import json

from django.test import RequestFactory, SimpleTestCase

from school_platform import errors


class ErrorHandlerTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/api/private-resource/')

    def assert_generic_response(self, response, status_code, expected_message):
        self.assertEqual(response.status_code, status_code)
        body = json.loads(response.content)
        self.assertEqual(body, {'error': expected_message})
        self.assertNotIn('private-stack-or-secret', response.content.decode())

    def test_bad_request(self):
        response = errors.bad_request(self.request, Exception('private-stack-or-secret'))
        self.assert_generic_response(response, 400, '请求格式不正确')

    def test_permission_denied(self):
        response = errors.permission_denied(self.request, Exception('private-stack-or-secret'))
        self.assert_generic_response(response, 403, '没有权限执行此操作')

    def test_page_not_found(self):
        response = errors.page_not_found(self.request, Exception('private-stack-or-secret'))
        self.assert_generic_response(response, 404, '请求的资源不存在')

    def test_server_error(self):
        response = errors.server_error(self.request)
        self.assert_generic_response(response, 500, '服务器内部错误，请稍后重试')
