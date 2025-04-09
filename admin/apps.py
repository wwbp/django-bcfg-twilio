from django.contrib.admin.apps import AdminConfig


class ChatAdmin(AdminConfig):
    default_site = "admin.admin.MyAdminSite"
