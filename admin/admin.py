from django.contrib import admin

from django.urls import include, path


class MyAdminSite(admin.AdminSite):
    def get_urls(self):
        self._registry = admin.site._registry
        admin_urls = super().get_urls()
        custom_urls = [
            path("test/", include("tester.urls"), name="tester"),
        ]
        return custom_urls + admin_urls  # custom urls must be at the beginning

    site_header = "WWBP - BCFG - AI Chatbot Admin Site"
