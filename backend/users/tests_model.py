"""
users Model + Serializer 单元测试
运行: cd backend && python manage.py test users.tests_model
"""
from django.test import TestCase
from users.models import CustomUser
from users.serializers import LoginSerializer, UserSerializer


class CustomUserModelTest(TestCase):
    """CustomUser 模型"""

    def test_create_teacher(self):
        """创建老师"""
        u = CustomUser.objects.create_user(
            username='teacher_zhang', password='test123', role='teacher',
            display_name='张老师', managed_grade='七年级'
        )
        self.assertEqual(u.role, 'teacher')
        self.assertEqual(u.managed_grade, '七年级')
        self.assertTrue(u.check_password('test123'))

    def test_create_student(self):
        """创建学生"""
        u = CustomUser.objects.create_user(
            username='7-1-05', password='pass', role='student',
            grade='七年级', class_num='1', student_number='05', display_name='李明'
        )
        self.assertEqual(u.role, 'student')
        self.assertEqual(u.grade, '七年级')
        self.assertEqual(u.class_num, '1')
        self.assertEqual(u.student_number, '05')

    def test_str_student_with_grade_classnum(self):
        """学生 __str__ = username (grade+classnum)"""
        u = CustomUser.objects.create_user(
            username='7-1-05', password='x', role='student',
            grade='七年级', class_num='1', student_number='05'
        )
        self.assertEqual(str(u), '7-1-05 (七年级1)')

    def test_str_student_no_grade(self):
        """无年级/班级 → __str__ = username"""
        u = CustomUser.objects.create_user(username='user_no_grade', password='x', role='student')
        self.assertEqual(str(u), 'user_no_grade')

    def test_str_teacher_no_grade_class(self):
        """老师无 grade/class_num → __str__ = username"""
        u = CustomUser.objects.create_user(username='alex', password='x', role='teacher')
        self.assertEqual(str(u), 'alex')

    def test_role_default_is_student(self):
        """默认 role='student'"""
        u = CustomUser.objects.create_user(username='default_role', password='x')
        self.assertEqual(u.role, 'student')

    def test_plain_password_saved(self):
        """plain_password 明文保存"""
        u = CustomUser.objects.create_user(
            username='stu', password='secret123', role='student',
            grade='七年级', class_num='1', student_number='01',
            plain_password='secret123'
        )
        self.assertEqual(u.plain_password, 'secret123')

    def test_managed_grade_for_teacher(self):
        """老师可设置 managed_grade"""
        u = CustomUser.objects.create_user(
            username='teacher_grade', password='x', role='teacher',
            managed_grade='八年级'
        )
        self.assertEqual(u.managed_grade, '八年级')

    def test_teacher_not_student(self):
        """role='teacher' 时 grade/class_num/managed_grade 都可以有值"""
        u = CustomUser.objects.create_user(
            username='dual', password='x', role='teacher',
            grade='老师所属年级', managed_grade='管理年级',
            display_name='双角色'
        )
        # teacher 也可以有 grade（取决于业务需求）
        self.assertEqual(u.role, 'teacher')


class LoginSerializerTest(TestCase):
    """LoginSerializer 字段校验"""

    def test_valid_student_fields(self):
        """学生登录字段全传 → is_valid=True"""
        data = {
            'grade': '七年级',
            'class_num': '1',
            'student_number': '05',
            'password': 'test123',
        }
        s = LoginSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['grade'], '七年级')

    def test_valid_teacher_fields(self):
        """老师登录（username + password）→ is_valid=True"""
        data = {'username': 'alex', 'password': 'teacher123'}
        s = LoginSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['username'], 'alex')

    def test_missing_password(self):
        """缺少 password → is_valid=False"""
        data = {'username': 'alex', 'grade': '七年级'}
        s = LoginSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('password', s.errors)

    def test_teacher_missing_username(self):
        """老师路径缺少 username（只有 grade/class_num）→ is_valid=True
        原因：LoginSerializer 没有自定义校验，字段都 required=False
        业务校验在 LoginView 层面"""
        data = {'grade': '七年级', 'class_num': '1', 'student_number': '01', 'password': 'x'}
        s = LoginSerializer(data=data)
        self.assertTrue(s.is_valid())  # 字段层面通过

    def test_all_fields_empty_still_valid(self):
        """空字段（只有 password）→ is_valid=True"""
        s = LoginSerializer(data={'password': 'x'})
        self.assertTrue(s.is_valid())  # 其他字段可选

    def test_only_username_and_password(self):
        """只有 username+password → is_valid=True（老师路径）"""
        s = LoginSerializer(data={'username': 'alex', 'password': 'x'})
        self.assertTrue(s.is_valid())


class UserSerializerTest(TestCase):
    """UserSerializer 序列化"""

    def test_serialize_student(self):
        """学生序列化包含所有字段"""
        u = CustomUser.objects.create_user(
            username='stu_s', password='x', role='student',
            grade='七年级', class_num='2', student_number='03', display_name='王小明'
        )
        s = UserSerializer(u)
        self.assertEqual(s.data['username'], 'stu_s')
        self.assertEqual(s.data['role'], 'student')
        self.assertEqual(s.data['grade'], '七年级')
        self.assertEqual(s.data['class_num'], '2')
        self.assertEqual(s.data['student_number'], '03')
        self.assertEqual(s.data['display_name'], '王小明')
        self.assertNotIn('plain_password', s.data)  # 不泄露密码
