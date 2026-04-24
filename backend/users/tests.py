"""
users (学生/老师认证) API 测试套件
运行: cd backend && python manage.py test users
"""
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token
from .models import CustomUser


def make_teacher(username='teacher_test', managed_grade='七年级'):
    u = CustomUser.objects.create_user(
        username=username, password='pass123',
        role='teacher', display_name='测试老师',
        managed_grade=managed_grade
    )
    return u

def make_student(grade='七年级', class_num='1', student_number='01',
                  display_name='张三', password='pass123'):
    username = f'{grade}-{class_num}-{student_number}'
    # 避免测试间冲突
    if CustomUser.objects.filter(username=username, role='student').exists():
        import uuid
        username = f'{username}-{uuid.uuid4().hex[:4]}'
    u = CustomUser.objects.create_user(
        username=username, password=password, role='student',
        grade=grade, class_num=class_num, student_number=student_number,
        display_name=display_name, plain_password=password
    )
    return u

def get_token(user):
    return Token.objects.get_or_create(user=user)[0].key


# ─── 登录测试 ─────────────────────────────────────────────────────────────

class LoginAPITest(APITestCase):
    """POST /api/auth/login/"""

    def setUp(self):
        self.teacher = make_teacher(username='teacher_login')
        self.student = make_student(
            grade='七年级', class_num='1', student_number='05',
            display_name='李四', password='stu123'
        )

    def test_login_teacher_with_username_password(self):
        """老师用 username + password 登录"""
        resp = self.client.post('/api/auth/login/', {
            'username': 'teacher_login',
            'password': 'pass123',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['user']['role'], 'teacher')
        self.assertIn('token', resp.data)

    def test_login_student_with_grade_class_number(self):
        """学生用 grade+class_num+student_number+password 登录"""
        resp = self.client.post('/api/auth/login/', {
            'grade': '七年级',
            'class_num': '1',
            'student_number': '05',
            'password': 'stu123',
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['user']['role'], 'student')
        self.assertEqual(resp.data['user']['display_name'], '李四')
        self.assertIn('token', resp.data)

    def test_login_wrong_password(self):
        """密码错误返回 401"""
        resp = self.client.post('/api/auth/login/', {
            'grade': '七年级',
            'class_num': '1',
            'student_number': '05',
            'password': 'wrongpass',
        }, format='json')
        self.assertEqual(resp.status_code, 401)
        self.assertIn('密码错误', resp.data['error'])

    def test_login_nonexistent_student(self):
        """不存在的学生返回 401"""
        resp = self.client.post('/api/auth/login/', {
            'grade': '七年级',
            'class_num': '9',
            'student_number': '99',
            'password': 'any',
        }, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_login_wrong_teacher_credentials(self):
        """老师用户名或密码错误"""
        resp = self.client.post('/api/auth/login/', {
            'username': 'teacher_login',
            'password': 'wrong',
        }, format='json')
        self.assertEqual(resp.status_code, 401)
        self.assertIn('用户名或密码错误', resp.data['error'])

    def test_login_missing_params(self):
        """参数不全返回 400"""
        resp = self.client.post('/api/auth/login/', {
            'grade': '七年级',
            # 缺少 class_num 和 student_number
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_login_no_params(self):
        """完全不提供参数"""
        resp = self.client.post('/api/auth/login/', {}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_login_creates_token(self):
        """登录成功应返回 token（不重复创建）"""
        resp = self.client.post('/api/auth/login/', {
            'username': 'teacher_login',
            'password': 'pass123',
        }, format='json')
        token_key = resp.data['token']
        self.assertEqual(Token.objects.filter(key=token_key).count(), 1)


# ─── 注册测试 ─────────────────────────────────────────────────────────────

class RegisterAPITest(APITestCase):
    """POST /api/auth/register/"""

    def test_register_success(self):
        """正确参数注册成功"""
        resp = self.client.post('/api/auth/register/', {
            'grade': '七年级',
            'class_num': '3',
            'student_number': '15',
            'display_name': '王小明',
            'password': 'pass123',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['user']['display_name'], '王小明')
        self.assertEqual(resp.data['user']['role'], 'student')
        self.assertIn('token', resp.data)
        # 用户实际已创建
        self.assertTrue(
            CustomUser.objects.filter(
                grade='七年级', class_num='3', student_number='15', role='student'
            ).exists()
        )

    def test_register_duplicate_student(self):
        """同名学生（grade+class_num+student_number 重复）应返回 400"""
        make_student(grade='七年级', class_num='2', student_number='10', display_name='重复')
        resp = self.client.post('/api/auth/register/', {
            'grade': '七年级',
            'class_num': '2',
            'student_number': '10',
            'display_name': '另一个',
            'password': 'pass123',
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('已存在', resp.data['error'])

    def test_register_missing_fields(self):
        """缺少必要字段返回 400"""
        for missing in ['grade', 'class_num', 'student_number', 'password', 'display_name']:
            data = {
                'grade': '七年级', 'class_num': '1',
                'student_number': '01', 'display_name': 'test', 'password': 'pass'
            }
            data.pop(missing)
            resp = self.client.post('/api/auth/register/', data, format='json')
            self.assertEqual(resp.status_code, 400, f'缺少 {missing} 应返回 400')

    def test_register_name_field_alias(self):
        """display_name 可用 name 别名"""
        resp = self.client.post('/api/auth/register/', {
            'grade': '八年级', 'class_num': '1', 'student_number': '20',
            'name': '用name字段',   # ← display_name 的别名
            'password': 'pass123',
        }, format='json')
        self.assertEqual(resp.status_code, 201)

    def test_register_auto_login(self):
        """注册后自动登录，返回 token"""
        resp = self.client.post('/api/auth/register/', {
            'grade': '高一', 'class_num': '1', 'student_number': '01',
            'display_name': '新生', 'password': 'pass123',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.data.get('token'))


# ─── 登出测试 ─────────────────────────────────────────────────────────────

class LogoutAPITest(APITestCase):
    """POST /api/auth/logout/"""

    def test_logout_success(self):
        """登录后登出"""
        student = make_student()
        token = get_token(student)
        resp = self.client.post('/api/auth/logout/', HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(resp.status_code, 200)
        # token 已被删除
        self.assertFalse(Token.objects.filter(user=student).exists())

    def test_logout_without_token(self):
        """未登录登出返回 401"""
        resp = self.client.post('/api/auth/logout/')
        self.assertEqual(resp.status_code, 401)


# ─── 当前用户测试 ─────────────────────────────────────────────────────────

class MeAPITest(APITestCase):
    """GET /api/auth/me/"""

    def test_me_as_teacher(self):
        """老师获取自身信息"""
        teacher = make_teacher()
        token = get_token(teacher)
        resp = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['role'], 'teacher')
        self.assertEqual(resp.data['display_name'], '测试老师')

    def test_me_as_student(self):
        """学生获取自身信息"""
        student = make_student(display_name='学生本人')
        token = get_token(student)
        resp = self.client.get('/api/auth/me/', HTTP_AUTHORIZATION=f'Token {token}')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['role'], 'student')
        self.assertEqual(resp.data['display_name'], '学生本人')

    def test_me_unauthenticated(self):
        """未登录返回 401"""
        resp = self.client.get('/api/auth/me/')
        self.assertEqual(resp.status_code, 401)


# ─── 学生管理（老师操作）─────────────────────────────────────────────────

class StudentManageAPITest(APITestCase):
    """GET/PUT/DELETE /api/auth/<user_id>/"""

    def setUp(self):
        self.teacher = make_teacher()
        self.teacher_token = get_token(self.teacher)
        self.student = make_student(
            grade='七年级', class_num='2', student_number='08',
            display_name='待管理学生', password='stu123'
        )
        self.student_token = get_token(self.student)

    def test_teacher_get_student_detail(self):
        """老师查看学生详情（含 plain_password）"""
        resp = self.client.get(
            f'/api/auth/{self.student.id}/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['display_name'], '待管理学生')
        self.assertEqual(resp.data['plain_password'], 'stu123')

    def test_teacher_update_student(self):
        """老师编辑学生信息"""
        resp = self.client.put(
            f'/api/auth/{self.student.id}/',
            {'display_name': '已改名', 'class_num': '5'},
            format='json',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['student']['display_name'], '已改名')
        self.assertEqual(resp.data['student']['class_num'], '5')

    def test_teacher_update_student_password(self):
        """老师修改学生密码"""
        resp = self.client.put(
            f'/api/auth/{self.student.id}/',
            {'password': 'newpass'},
            format='json',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 200)
        # 新密码能登录
        login = self.client.post('/api/auth/login/', {
            'grade': '七年级', 'class_num': '2',
            'student_number': '08', 'password': 'newpass'
        }, format='json')
        self.assertEqual(login.status_code, 200)

    def test_teacher_delete_student(self):
        """老师删除学生"""
        stu_id = self.student.id
        resp = self.client.delete(
            f'/api/auth/{stu_id}/',
            HTTP_AUTHORIZATION=f'Token {self.teacher_token}'
        )
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(CustomUser.objects.filter(id=stu_id, role='student').exists())

    def test_student_cannot_manage_others(self):
        """学生不能管理其他学生（返回 403）"""
        other = make_student(grade='八年级', class_num='1', student_number='99',
                              display_name='其他人')
        resp = self.client.get(
            f'/api/auth/{other.id}/',
            HTTP_AUTHORIZATION=f'Token {self.student_token}'
        )
        self.assertEqual(resp.status_code, 403)

    def test_teacher_get_nonexistent_student(self):
        """查看不存在的学生返回 404"""
        resp = self.client.get('/api/auth/99999/', HTTP_AUTHORIZATION=f'Token {self.teacher_token}')
        self.assertEqual(resp.status_code, 404)

    def test_unauthenticated_rejected(self):
        """未登录全部拒绝"""
        for method, url in [
            ('get', f'/api/auth/{self.student.id}/'),
            ('put', f'/api/auth/{self.student.id}/'),
            ('delete', f'/api/auth/{self.student.id}/'),
        ]:
            fn = getattr(self.client, method)
            resp = fn(url, format='json')
            self.assertEqual(resp.status_code, 401, f'{method.upper()} {url} 应返回 401')
