# tests/StudentModule/test_student_number.py
import unittest, tempfile, os, sqlite3, sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
import server

class TestStudentNumberField(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.tmp.close()
        self.orig_db = server.DB_FILE
        server.DB_FILE = self.tmp.name
        server.setup_database()
    def tearDown(self):
        server.DB_FILE = self.orig_db
        try:
            os.unlink(self.tmp.name)
        except:
            pass

    def test_schema_contains_student_number_and_index(self):
        conn = sqlite3.connect(server.DB_FILE)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cur.fetchall()]
        self.assertIn('student_number', cols)
        # 检查索引是否存在
        cur.execute("PRAGMA index_list('users')")
        indexes = [r[1] for r in cur.fetchall()]
        # 索引名可能为 idx_users_grade_class_stuno
        self.assertTrue(any('stuno' in (name or '') for name in indexes))
        conn.close()

    def test_register_with_student_number_and_readback(self):
        ok, msg = server.register_user('七年级','1班','stuA','pwdA','001')
        self.assertTrue(ok)
        students = server.get_all_students()
        # 找到对应记录并检查学号
        found = [s for s in students if s[4] == 'stuA']
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][3], '001')  # student_number 在 index 3

    def test_duplicate_student_number_within_class_rejected(self):
        server.register_user('七年级','1班','stuA','pwdA','001')
        ok, msg = server.register_user('七年级','1班','stuB','pwdB','001')
        self.assertFalse(ok)
        self.assertIn('学号', msg)

    def test_update_student_number_and_conflict(self):
        server.register_user('七年级','1班','stuA','pwdA','001')
        server.register_user('七年级','1班','stuB','pwdB','002')
        # 获取 stuA id
        students = server.get_all_students()
        a = [s for s in students if s[4]=='stuA'][0]
        aid = a[0]
        ok, msg = server.update_student(aid, '七年级','1班','stuA','pwdA','003')
        self.assertTrue(ok)
        # 尝试将 A 改为已存在的 002
        ok2, msg2 = server.update_student(aid, '七年级','1班','stuA','pwdA','002')
        self.assertFalse(ok2)
        self.assertIn('学号', msg2)

    def test_legacy_db_no_student_number_returns_placeholder(self):
        # 手工创建旧表结构（没有 student_number 列）
        conn = sqlite3.connect(server.DB_FILE)
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS users")
        cur.execute('''CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            grade TEXT NOT NULL,
            class_num TEXT NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            UNIQUE(grade, class_num, username)
        )''')
        conn.commit()
        # 插入一条记录
        cur.execute("INSERT INTO users (grade,class_num,username,password) VALUES (?,?,?,?)",
                    ('七年级','1班','legacy','pw'))
        conn.commit()
        conn.close()
        # 现在调用 get_all_students() 应返回 student_number 占位符 '-'
        rows = server.get_all_students()
        self.assertEqual(rows[0][3], '-')  # 占位符位置
    def test_delete_student_removes_scores(self):
        server.register_user('七年级','1班','stuA','pwdA','001')
        students = server.get_all_students()
        aid = [s for s in students if s[4]=='stuA'][0][0]
        # 插入 scores
        conn = sqlite3.connect(server.DB_FILE)
        cur = conn.cursor()
        cur.execute("INSERT INTO scores (grade,class_num,username,problem_id,score,submission_time) VALUES (?,?,?,?,?,?)",
                    ('七年级','1班','stuA',1,90,'2025-01-01 00:00:00'))
        conn.commit()
        conn.close()
        ok, msg = server.delete_student(aid)
        self.assertTrue(ok)
        # scores 应为空
        conn = sqlite3.connect(server.DB_FILE)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM scores WHERE username=?", ('stuA',))
        cnt = cur.fetchone()[0]
        conn.close()
        self.assertEqual(cnt, 0)

if __name__ == '__main__':
    unittest.main()