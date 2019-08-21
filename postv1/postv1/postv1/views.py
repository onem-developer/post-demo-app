import onemsdk
import datetime
import jwt
import pytz
import random
import requests
import string

from ago import human

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.views.generic import View as _View

from onemsdk.schema.v1 import (
    Response, Menu, MenuItem, Form, FormItemContent, FormItemContentType,
    FormMeta
)


class View(_View):
    @method_decorator(csrf_exempt)
    def dispatch(self, *a, **kw):
        return super(View, self).dispatch(*a, **kw)

    def get_user(self):
        token = self.request.headers.get('Authorization')
        if token is None:
            raise PermissionDenied

        data = jwt.decode(token.replace('Bearer ', ''), key='87654321')
        user, created = User.objects.get_or_create(id=data['sub'])

        return user

    def to_response(self, content):
        response = Response(content=content)

        return HttpResponse(response.json(), content_type='application/json')


class HomeView(View):
    http_method_names = ['get','post', 'put']

    def get(self, request, post_id=None):
        user = self.get_user()
        if user.username == '':
            form_items = [
                FormItemContent(type=FormItemContentType.string,
                                name='username',
                                description='Please choose a username',
                                header='MENU',
                                footer='Send username')
            ]
            content = Form(body=form_items,
                           method='POST',
                           path=reverse('home'),
                           meta=FormMeta(confirmation_needed=False,
                                         completion_status_in_header=False,
                                         completion_status_show=False))
        else:
            menu_items = [
                MenuItem(description='Add post',
                         method='GET',
                         path=reverse('add_post')),
                MenuItem(description='My posts',
                         method='GET',
                         path=reverse('my_posts'))
            ]
           
            content = Menu(body=menu_items)

        if not cache.get('posts'):
            cache.set('posts', [])

        return self.to_response(content)

    def post(self, request):
        user = self.get_user()
        User.objects.filter(id=user.id).update(username=request.POST['username'])
        return HttpResponseRedirect(reverse('home'))


class AddPostView(View):
    http_method_names = ['get', 'post']

    def get(self, request):
        form_items = [
            FormItemContent(type=FormItemContentType.string,
                     name='title',
                     description='Give your new post a title (maximum 64 characters)',
                     header='add',
                     footer='Reply with post title or BACK'),
            FormItemContent(type=FormItemContentType.string,
                     name='description',
                     description='Send post content (max 50 words)',
                     header='add',
                     footer='Reply with post content or BACK'),
        ]
        form = Form(body=form_items,
                    method='POST',
                    path=reverse('add_post'),
                    meta=FormMeta(confirmation_needed=False,
                                  completion_status_in_header=False,
                                  completion_status_show=False))

        return self.to_response(form)

    def post(self, request):
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        expires_at = now + datetime.timedelta(days=14)
        user_id = self.get_user().id

        # since we don't create DB records, we don't have a post id to use it
        # for hashids encoding thus we generate a random code
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        new_post = {
            'user': self.get_user(),
            'title': request.POST['title'],
            'description': request.POST['description'],
            'expires_at': expires_at,
            'code': code
        }

        # save post in cache
        existing_posts = cache.get('posts')
        if existing_posts:
            cache.set('posts', cache.get('posts') + [new_post])
        else:
            cache.set('posts', [new_post])
        cache.set('new_post', True)

        return HttpResponseRedirect(reverse('post_detail', args=[new_post['code']]))


class MyPostsListView(View):
    http_method_names = ['get']

    def get(self, request):
        menu_items = []

        posts = cache.get('posts')
        if posts:
            for post in posts:
                menu_items.append(
                    MenuItem(description=u'{}..'.format(post['title'][:15]),
                             method='GET',
                             path=reverse('post_detail', args=[post['code']]))
                )
        else:
            menu_items.append(
                MenuItem(description='You currently have no posts.')
            )
        content = Menu(body=menu_items, footer='Reply MENU')
        
        return self.to_response(content)


class PostDetailView(View):
    http_method_names = ['get']

    def get(self, request, code):
        post = [post for post in cache.get('posts') if post['code'] == code][0]

        menu_items = []
        body_pre = [
            post['description'],
            'Author: {}'.format(post['user'].username),
            'Expires in: {}'.format(human(post['expires_at'])),
            'Code: {}'.format(post['code']),
        ]

        # check to see if we have notifications set in cache for this post
        if cache.get('new_post'):
            body_pre.insert(0, 'Post successfuly created!')
            cache.delete('new_post')

        menu_items.extend([MenuItem(description=u'\n'.join(body_pre))])

        # TODO: get the post title from cache
        content = Menu(body=menu_items, header=post['title'], footer='Reply MENU')

        return self.to_response(content)
