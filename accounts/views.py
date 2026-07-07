from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from .forms import RegisterForm, LoginForm, ProfileForm
from orders.models import Order


def _safe_next_url(request):
    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return ''


def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Bem-vinda, {user.full_name}! Conta criada com sucesso.')
            return redirect(_safe_next_url(request) or 'home')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form, 'next_url': _safe_next_url(request)})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bem-vinda, {user.full_name or user.username}!')
            return redirect(_safe_next_url(request) or 'home')
        else:
            messages.error(request, 'E-mail ou senha incorretos.')
    else:
        form = LoginForm()
    return render(request, 'accounts/login.html', {'form': form, 'next_url': _safe_next_url(request)})


def logout_view(request):
    logout(request)
    messages.info(request, 'Você saiu da sua conta.')
    return redirect('home')


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Dados atualizados com sucesso!')
            return redirect('profile')
    else:
        form = ProfileForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def my_orders(request):
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    return render(request, 'accounts/orders.html', {'orders': orders})


@login_required
def order_detail(request, order_number):
    try:
        order = Order.objects.get(order_number=order_number, customer=request.user)
    except Order.DoesNotExist:
        messages.error(request, 'Pedido não encontrado.')
        return redirect('my_orders')
    return render(request, 'accounts/order_detail.html', {
        'order': order,
        'active_payment': order.active_payment,
        'payment_attempts': order.payments.order_by('-created_at'),
        'payment_choices': Order.PAYMENT_CHOICES,
    })
