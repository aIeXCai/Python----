from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from users.models import CustomUser

from ai_courses.models import AIChoiceQuestion, AIQuizSession, AIUnit
from ai_courses.quiz_attempt_services import start_or_resume_attempt
from ai_courses.quiz_services import close_quiz, create_quiz, publish_quiz
from ai_courses.quiz_settlement_services import (
    request_settlement,
    request_system_settlement,
)


MARK = '【演示】'
DEMO_PASSWORD = 'Demo123456!'


QUESTION_SPECS = (
    ('easy', 'AI 基础', '以下哪项最符合人工智能的含义？',
     '让机器完成通常需要人类智能的任务', '让电脑永不关机', '只提高网络速度',
     '把文件变得更大', '人工智能关注感知、推理、学习和决策等能力。'),
    ('easy', '数据', '训练一个分类模型通常需要什么？',
     '带有代表性的训练数据', '只需要空文件夹', '只修改屏幕亮度',
     '只增加键盘数量', '训练数据决定了模型可以学习到的模式。'),
    ('easy', '代码阅读', '下面代码输出什么？\n```python\nprint(2 + 3)\n```',
     '`5`', '`23`', '`2 + 3`', '没有输出', '加法先计算，再由 print 输出结果。'),
    ('easy', '安全', '使用生成式 AI 时，哪种做法更安全？',
     '核对重要答案并保护个人信息', '直接公开账号密码', '从不检查生成内容',
     '把隐私数据全部上传', '重要结论应核验，敏感信息不应上传。'),
    ('medium', '机器学习', '监督学习与无监督学习的主要区别是什么？',
     '监督学习通常使用带标签数据', '监督学习不需要数据', '无监督学习只能处理图片',
     '二者完全相同', '标签是监督信号。'),
    ('medium', '代码阅读',
     '执行代码后 `result` 是多少？\n```python\nvalues = [1, 2, 3]\nresult = sum(values)\n```',
     '`6`', '`3`', '`[1, 2, 3]`', '`None`', 'sum 会对列表元素求和。'),
    ('medium', '算法偏差', '减少模型偏差更合适的做法是？',
     '检查数据代表性并分群评估', '隐藏全部评估结果', '只测试一个样本',
     '删除所有少数样本', '应从数据和评估两端检查不同群体表现。'),
    ('medium', '提示词', '希望模型稳定输出 JSON，哪种提示更合适？',
     '明确字段、格式并给出示例', '只输入“随便回答”', '不说明任何要求',
     '每次随机改变字段名', '清晰的结构约束和示例有助于稳定输出。'),
    ('hard', '评估', '分类数据极不平衡时，只看准确率可能有什么问题？',
     '可能掩盖少数类识别很差', '准确率一定等于召回率', '准确率无法计算',
     '模型一定不会过拟合', '应结合精确率、召回率、F1 等指标。'),
    ('hard', '代码阅读',
     '下面代码的输出是？\n```python\nitems = [1, 2, 3, 4]\n'
     'print([x * x for x in items if x % 2 == 0])\n```',
     '`[4, 16]`', '`[1, 9]`', '`[2, 4]`', '`[1, 4, 9, 16]`',
     '先筛选偶数 2、4，再分别平方。'),
    ('hard', '泛化', '模型训练集表现很好、测试集表现明显较差，最可能是？',
     '过拟合', '欠拟合一定消失', '数据完全没有特征', '程序没有运行',
     '训练好而测试差是典型的泛化不足。'),
    ('hard', '检索增强', 'RAG 系统中，检索步骤的核心作用是？',
     '为生成提供相关外部资料', '永久修改模型参数', '替代所有安全校验',
     '把问题随机打乱', '检索增强生成先找相关资料，再结合资料回答。'),
)


QUIZ_SPECS = (
    ('【演示】AI 基础概念小测', 5, {'easy': 2, 'medium': 2, 'hard': 1}, 20),
    ('【演示】代码阅读与安全', 4, {'easy': 1, 'medium': 2, 'hard': 1}, 15),
    ('【演示】AI 综合复习', 6, {'easy': 2, 'medium': 2, 'hard': 2}, 25),
)


class Command(BaseCommand):
    help = '创建本地 AI 混合小测统计演示数据（不修改现有编程题）'

    @transaction.atomic
    def handle(self, *args, **options):
        if AIQuizSession.objects.filter(title__startswith=MARK).exists():
            self.stdout.write(self.style.WARNING('演示小测已存在，本次未重复创建。'))
            return
        try:
            teacher = CustomUser.objects.get(username='alex', is_superuser=True)
        except CustomUser.DoesNotExist as exc:
            raise CommandError('找不到超级管理员 alex，无法创建演示数据。') from exc

        students = self._students()
        section = self._question_bank(teacher)
        quizzes = self._quizzes(teacher, section)
        self._attempts(students, quizzes)
        close_quiz(
            actor=teacher,
            session_id=quizzes[2].pk,
            expected_version=quizzes[2].management_version,
        )
        self.stdout.write(self.style.SUCCESS(
            '演示数据创建完成：6 名学生、12 道选择题、3 份小测；'
            f'学生账号 ai_demo_01～ai_demo_06，统一密码 {DEMO_PASSWORD}。'
        ))

    def _students(self):
        students = []
        for index, name in enumerate(('小智', '小雨', '小航', '小禾', '小满', '小新'), 1):
            username = f'ai_demo_{index:02d}'
            student = CustomUser.objects.filter(username=username).first()
            if student is None:
                student = CustomUser(username=username)
            student.role = 'student'
            student.display_name = f'演示学生·{name}'
            student.grade = '七年级'
            student.class_num = '3'
            student.student_number = str(index)
            student.is_active = True
            student.set_password(DEMO_PASSWORD)
            student.full_clean()
            student.save()
            students.append(student)
        return students

    def _question_bank(self, teacher):
        root = AIUnit(
            grade='七年级', name='demo_ai', display_name='【演示】人工智能基础',
            order=90, created_by=teacher,
        )
        root.full_clean()
        root.save()
        section = AIUnit(
            grade='七年级', parent=root, name='demo_concepts',
            display_name='【演示】AI 概念与代码阅读', order=1, created_by=teacher,
        )
        section.full_clean()
        section.save()
        for difficulty, category, text, a, b, c, d, explanation in QUESTION_SPECS:
            question = AIChoiceQuestion(
                unit=section, difficulty=difficulty, category=category, text=text,
                option_a=a, option_b=b, option_c=c, option_d=d, answer='A',
                explanation=explanation, created_by=teacher,
            )
            question.full_clean()
            question.save()
        return section

    def _quizzes(self, teacher, section):
        quizzes = []
        for title, count, ratio, minutes in QUIZ_SPECS:
            quiz = create_quiz(actor=teacher, values={
                'title': title,
                'content_grade': '七年级',
                'choice_unit_ids': [section.pk],
                'choice_question_count': count,
                'choice_difficulty_ratio': ratio,
                'choice_points': '100.0',
                'programming_items': [],
                'time_limit': minutes,
                'audience': [{'scope_type': 'grade_all', 'grade': '七年级'}],
            })
            quizzes.append(publish_quiz(
                actor=teacher,
                session_id=quiz.pk,
                expected_version=quiz.management_version,
            ))
        return quizzes

    @staticmethod
    def _finish(student, quiz, correct_count):
        attempt, _created = start_or_resume_attempt(student, quiz.pk)
        choices = [
            item for item in attempt.snapshot_json['items']
            if item['type'] == 'choice'
        ]
        answers = {}
        for index, item in enumerate(choices):
            correct = item['correct_display_option']
            answers[item['item_id']] = (
                correct if index < correct_count
                else next(letter for letter in 'ABCD' if letter != correct)
            )
        return request_settlement(
            user=student,
            session_id=quiz.pk,
            attempt_id=attempt.pk,
            reason='submitted',
            final_answers=answers,
            revision=attempt.answer_revision,
        )

    def _attempts(self, students, quizzes):
        # 小测 1：历史最好与最近成绩不同，并包含未开始、作答中和超时。
        self._finish(students[0], quizzes[0], 5)
        self._finish(students[0], quizzes[0], 3)
        self._finish(students[1], quizzes[0], 4)
        self._finish(students[2], quizzes[0], 2)
        start_or_resume_attempt(students[4], quizzes[0].pk)
        timed_out, _created = start_or_resume_attempt(students[5], quizzes[0].pk)
        request_system_settlement(timed_out.pk, 'timed_out')

        # 小测 2：形成不同薄弱题分布，并包含一次重做和一份作答中试卷。
        self._finish(students[0], quizzes[1], 3)
        self._finish(students[1], quizzes[1], 2)
        self._finish(students[1], quizzes[1], 4)
        self._finish(students[2], quizzes[1], 1)
        self._finish(students[3], quizzes[1], 3)
        start_or_resume_attempt(students[5], quizzes[1].pk)

        # 小测 3：多档已结算成绩，最后关闭场次。
        self._finish(students[0], quizzes[2], 6)
        self._finish(students[1], quizzes[2], 5)
        self._finish(students[2], quizzes[2], 4)
        self._finish(students[3], quizzes[2], 3)
        self._finish(students[4], quizzes[2], 2)
