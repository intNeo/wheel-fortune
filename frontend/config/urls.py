from django.urls import path
from wheel.auth_views import login, logout
from wheel.views import index, spin, health
urlpatterns = [path('login/', login), path('logout/', logout), path('', index), path('api/spin', spin), path('healthz', health)]
