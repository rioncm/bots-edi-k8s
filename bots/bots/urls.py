# -*- coding: utf-8 -*-
"""
Bots urls
"""

from django.contrib import admin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import views as auth_views
from django.urls import include, re_path

from . import botsglobal
from . import views
from . import healthcheck


staff_required = user_passes_test(lambda u: u.is_staff)
superuser_required = user_passes_test(lambda u: u.is_superuser)
run_permission = user_passes_test(lambda u: u.has_perm('bots.change_mutex'))


# Bots URL patterns
bots_paths = [
    # Health checks (no auth required - for K8s probes)
    re_path(r'^health/live/?$', healthcheck.health_live, name='health_live'),
    re_path(r'^health/ready/?$', healthcheck.health_ready, name='health_ready'),
    re_path(r'^health/startup/?$', healthcheck.health_startup, name='health_startup'),
    re_path(r'^health/ping/?$', healthcheck.health_ping, name='health_ping'),
    # Main views - login required
    re_path(r'^home.*', login_required(views.home), name='home'),
    re_path(r'^incoming.*', login_required(views.incoming), name='incoming'),
    re_path(r'^outgoing.*', login_required(views.outgoing), name='outgoing'),
    re_path(r'^detail.*', login_required(views.detail), name='detail'),
    re_path(r'^process.*', login_required(views.process), name='process'),
    re_path(r'^document.*', login_required(views.document), name='document'),
    re_path(r'^reports.*', login_required(views.reports), name='reports'),
    re_path(r'^confirm.*', login_required(views.confirm), name='confirm'),
    re_path(r'^filer.*', login_required(views.filer), name='filer'),
    re_path(r'^srcfiler.*', login_required(views.srcfiler), name='srcfiler'),
    re_path(r'^logfiler.*', login_required(views.logfiler), name='logfiler'),
    # only staff
    re_path(r'^runengine.+', run_permission(views.runengine), name='runengine'),
    # only superuser
    re_path(r'^delete.*', superuser_required(views.delete), name='delete'),
    re_path(r'^plugin/index.*', superuser_required(views.plugin_index), name='plugin_index'),
    re_path(r'^plugin.*', superuser_required(views.plugin), name='plugin'),
    re_path(r'^plugout/index.*', superuser_required(views.plugout_index), name='plugout_index'),
    re_path(r'^plugout/backup.*', superuser_required(views.plugout_backup), name='plugout_backup'),
    re_path(r'^plugout.*', superuser_required(views.plugout), name='plugout'),
    re_path(r'^sendtestmail.*', superuser_required(views.sendtestmailmanagers), name='sendtestmail'),
    # catch-all
    re_path(r'^.*', views.index),
]

auth_paths = [
    # Auth
    re_path(
        r"^login.*", auth_views.LoginView.as_view(template_name="admin/login.html"),
        name="login",
    ),
    re_path(
        r"^logout.*", auth_views.LogoutView.as_view(next_page="/"),
        name="logout",
    ),
]
if botsglobal.ini.getboolean("webserver", "menu_changepassword", True):
    auth_paths += [
        re_path(
            r"^password_change/$", auth_views.PasswordChangeView.as_view(),
            name="password_change",
        ),
        re_path(
            r"^password_change/done/$", auth_views.PasswordChangeDoneView.as_view(),
            name="password_change_done",
        ),
    ]


urlpatterns = auth_paths + [
    # only staff
    # do not show django admin root page
    # re_path(r'^admin/$', login_required(views.home)),
    # do not show django admin root page
    # re_path(r'^admin/bots/$', login_required(views.home)),
    re_path(r'^admin/', admin.site.urls),
    # Bots urls
    re_path('bots/', include((bots_paths, 'bots'), namespace='bots')),
    re_path(r'^.*', views.index),
]

# pylint: disable=invalid-name
handler500 = 'bots.views.server_error'
