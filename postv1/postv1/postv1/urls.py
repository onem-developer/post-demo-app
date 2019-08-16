from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('add_post', views.AddPostView.as_view(), name='add_post'),
    path('my_posts', views.MyPostsListView.as_view(), name='my_posts'),
    path('post_detail/<str:code>/', views.PostDetailView.as_view(), name='post_detail'),
]

