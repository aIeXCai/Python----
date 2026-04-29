"""
URL configuration for school_platform project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/ai/', include('ai_courses.urls')),
    path('api/', include('info_tech.urls')),           # admin 路由 /api/admin/info/
    path('api/info/', include('info_tech.urls_student')),  # 学生路由 /api/info/
    path('api/chat/', include('chat.urls')),
]

# 开发环境：提供 media 文件访问
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
