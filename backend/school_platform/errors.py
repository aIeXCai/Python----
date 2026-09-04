from django.http import JsonResponse


def bad_request(request, exception=None):
    return JsonResponse({'error': '请求格式不正确'}, status=400)


def permission_denied(request, exception=None):
    return JsonResponse({'error': '没有权限执行此操作'}, status=403)


def page_not_found(request, exception=None):
    return JsonResponse({'error': '请求的资源不存在'}, status=404)


def server_error(request):
    return JsonResponse({'error': '服务器内部错误，请稍后重试'}, status=500)
