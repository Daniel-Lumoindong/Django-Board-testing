from django.db.models import Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404

from boards.forms import NewTopicForm, PostForm
from boards.models import Board, Topic, Post
from django.views.generic import UpdateView, ListView
from django.utils import timezone
# from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from boards.models import Post, Board
from django.urls import reverse

# Create your views here.


class BoardListView(ListView):
    # gantinya home
    model = Board
    context_object_name = 'boards'
    template_name = 'home.html'
    paginate_by = 15

    def get_queryset(self):
        queryset = Board.objects.all().order_by('id')
        return queryset


def home(request):
    boards = Board.objects.all()
    # boards_names = list()
    # for board in boards:
    #    boards_names.append(board.name)

    # response_html = '<br>'.join(boards_names)
    # return HttpResponse(response_html)
    return render(request, 'home.html', {'boards': boards})


class TopicListView(ListView):
    # gantinya board_topics
    model = Topic
    context_object_name = 'topics'
    template_name = 'topics.html'
    paginate_by = 15

    def get_context_data(self, **kwargs):
        kwargs['board'] = self.board
        return super().get_context_data(**kwargs)

    def get_queryset(self):
        self.board = get_object_or_404(Board, pk=self.kwargs.get('board_id'))
        queryset = self.board.topics.order_by(
            '-last_updated').annotate(replies=Count('posts')-1)
        return queryset


def board_topics(request, board_id):
    # another way to catch 404 error
    board = get_object_or_404(Board, pk=board_id)
    try:
        board = Board.objects.get(pk=board_id)
    except Board.DoesNotExist:
        raise Http404
    queryset = board.topics.order_by(
        '-last_updated').annotate(replies=Count('posts')-1)
    page = request.GET.get('page', 1)
    paginator = Paginator(queryset, 20)
    try:
        topics = paginator.page(page)
    except PageNotAnInteger:
        # fallback to the first page
        topics = paginator.page(1)
    except EmptyPage:
        # probably the user try to add a page number
        # in the url, so we fallback to the last page
        topics = paginator.page(paginator.num_pages)
    # topics = board.topics.order_by(
    #    '-last_updated').annotate(replies=Count('posts')-1)
    return render(request, 'topics.html', {'board': board, 'topics': topics})


@login_required
def new_topic(request, board_id):
    try:
        board = Board.objects.get(pk=board_id)
    except Board.DoesNotExist:
        raise Http404

    # user = User.objects.first()  # TODO: get the currently logged in user
    if request.method == 'POST':
        form = NewTopicForm(request.POST)
        if form.is_valid():
            topic = form.save(commit=False)
            topic.board = board
            # topic.starter = user
            topic.starter = request.user
            topic.save()
            # topic = form.save()
            post = Post.objects.create(
                message=form.cleaned_data.get('message'),
                topic=topic,
                created_by=request.user
            )
            return redirect('board_topics', board_id=board.pk)

    else:
        form = NewTopicForm()
        # subject = request.POST['subject']    # subject adalah name dari html
        # message = request.POST['message']
        # topic = Topic.objects.create(subject=subject, board=board, starter=user)
        # post = Post.objects.create(message=message, topic=topic, created_by=user)
        # return redirect('board_topics', board_id=board.pk)

    return render(request, 'new_topic.html', {'board': board, 'form': form})


# gantinya topic_post
class PostListView(ListView):
    model = Post
    context_object_name = 'posts'
    template_name = 'topic_posts.html'
    paginate_by = 2

    def get_queryset(self):
        try:
            self.topic = Topic.objects.get(pk=self.kwargs.get('topic_pk'))
        except self.topic.DoesNotExist:
            raise Http404
        queryset = self.topic.posts.order_by('created_at')
        return queryset

    def get_context_data(self, **kwargs):
        # Session key digunakan spy jika user nya sama, tidak perlu menambah view
        session_key = 'viewed_topic_{}'.format(self.topic.pk)
        if not self.request.session.get(session_key, False):
            self.topic.views += 1
            self.topic.save()
            self.request.session[session_key] = True

        kwargs['topic'] = self.topic
        return super().get_context_data(**kwargs)


def topic_posts(request, board_id, topic_pk):
    try:
        topic = Topic.objects.get(pk=topic_pk)
    except Topic.DoesNotExist:
        raise Http404
    topic.views += 1
    topic.save()
    # topic = get_object_or_404(Topic, board_pk=board_id, pk=topic_pk)
    return render(request, 'topic_posts.html', {'topic': topic})


def reply_topic(request, board_id, topic_id):
    try:
        topic = Topic.objects.get(pk=topic_id)
    except Topic.DoesNotExist:
        raise Http404
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.topic = topic
            post.created_by = request.user
            post.save()

            topic.last_updated = timezone.now()
            topic.save()

            topic_url = reverse('topic_posts', kwargs={
                                'board_id': board_id, 'topic_pk': topic_id})
            topic_post_url = '{url}?page={page}#{id}'.format(
                url=topic_url,
                id=post.pk,
                page=topic.get_page_count()
            )
            # return redirect('topic_posts', board_id=topic.board_id, topic_pk=topic.pk)
            return redirect(topic_post_url)
    else:
        form = PostForm()
    return render(request, 'reply_topic.html', {'topic': topic, 'form': form})


# @method_decorator(login_required, name='dispatch')
class PostUpdateView(LoginRequiredMixin, UpdateView):
    model = Post
    fields = ('message', )
    template_name = 'edit_post.html'
    pk_url_kwarg = 'post_pk'
    context_object_name = 'post'

    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(created_by=self.request.user)

    def form_valid(self, form):
        post = form.save(commit=False)
        post.updated_by = self.request.user
        post.updated_at = timezone.now()
        post.save()
        return redirect('topic_posts', board_id=post.topic.board.pk, topic_pk=post.topic.pk)
