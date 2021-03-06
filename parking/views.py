from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from parking.forms import *
from parking.models import Car, User, Log
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
import math
from django.utils import timezone
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
import json
import re


def index(request): # 초기화면 랜더
    form_log = LogForm()
    form_car = CarForm()
    form_user = UserForm()
    context = {
        'form_log': form_log,
        'form_car': form_car,
        'form_user': form_user,
    }
    return render(request, 'parking/index.html', context)


def car_in(request):
    if request.method == 'POST':
        # 차번호 검증
        car_num = request.POST['car_num']
        regex_car_num = re.compile('\d{2,3}[가-힣]{1}\d{4}$')
        check_car = regex_car_num.match(car_num)

        if check_car is None:
            check = {'check': '잘못된 형식 입니다 다시 입력해주세요'}
            return HttpResponse(json.dumps(check), content_type='application/json')
        else:
            if Log.objects.filter(car_number=car_num, car_stat=True).exists():
                already = {'already': '이미 입차된 차량입니다.'}
                return HttpResponse(json.dumps(already), content_type='application/json')
            else:
                try:  # 등록 유저일때
                    user_car = Car.objects.get(car_num=car_num, ticket_limit__gte=timezone.now())
                    log = Log(car_number=car_num, user_stat=True, pay_val='ticket', car_stat=True)
                    user = User.objects.get(id=user_car.user_id)
                    log.save()
                    context = {
                        'customer': user,
                        'ticket_limit': user_car.ticket_limit
                    }
                    # ajax로 화면을 그려주기위해 render to string 사용
                    html = render_to_string('parking/success_in.html', context)
                    user = {
                        'user': user_car.user.name + '님 입차성공입니다',
                        'html': html
                    }
                    return HttpResponse(json.dumps(user), content_type='application/json')
                except ObjectDoesNotExist as e:  # 등록 유저가 아닌경우
                    log = Log(car_number=car_num, user_stat=False, car_stat=True)
                    log.save()
                    context = {'customer': '고객'}
                    html = render_to_string('parking/success_in.html', context)
                    customer = {
                        'customer': '고객',
                        'ticket_limit': '정기권이 없습니다',
                        'html': html
                    }
                    return HttpResponse(json.dumps(customer), content_type='application/json')
    else:
        # get 요청시 404page
        return render(request, 'parking/404.html', {})


def calculate(request):
    if request.method == 'POST':
        form = LogForm(request.POST)
        if form.is_valid():
            log = form.save(commit=False) # 바로저장 하지 않고 작업처리
            car_num = log.car_number

            regex_car_num = re.compile('\d{2,3}[가-힣]{1}\d{4}$')
            check_car = regex_car_num.match(car_num)

            if check_car is None:
                return render(request, 'parking/wrong_request.html', {'message': '잘못된 요청입니다'})
            else:
                try:
                    if Log.objects.filter(car_number=log.car_number, car_stat=True).exists():
                        log_recent = Log.objects.get(car_number=log.car_number, car_stat=True)
                        user = log_recent.user_stat
                        if user:   # 회원인 경우 출차
                            log_recent.car_out = timezone.now()
                            log_recent.car_stat = False
                            log_recent.save()
                            user = Car.objects.get(car_num=log_recent.car_number)
                            context = {
                                'customer': user.user.name,
                                'out_time': log_recent.car_out,
                            }
                            return render(request, 'parking/success_out.html', context)
                        else:  # 비회원인 경우 계산으로 보냄
                            out_time = timezone.now()
                            log_recent.car_out = out_time
                            log_recent.save()
                            car_number = log.car_number
                            print(car_number)
                            return HttpResponseRedirect('./{}/'.format(car_number))
                    else:  # 입차 입차인 경우
                        return render(request, 'parking/wrong_request.html', {'message': '잘못된 요청입니다'})
                except ObjectDoesNotExist as e:  # 데이터베이스 오류
                    form = LogForm()
                    return render(request, 'parking/index.html', {'form': form})
        else:  # 폼 invalid
            form = LogForm()
            return render(request, 'parking/index.html', {'form': form})
    else:  # Get 요청
        return redirect('parking:index')


def car_out(request, car_number):
    if request.method == 'POST':
        try:
            form = CalcForm(request.POST)
            guest_car = Log.objects.get(car_number=car_number, car_stat=True)
            out_time = guest_car.car_out
            in_time = guest_car.car_in
            pay_val = math.ceil((out_time - in_time).seconds / 60) * 100
        except ObjectDoesNotExist as e:
            context = {'message': '잘못된 접근입니다.'}
            return render(request, 'parking/404.html', context)
        if form.is_valid():
            pay_balance = form.cleaned_data['pay_balance']
            if pay_balance == str(pay_val):
                guest_car.car_stat = False
                guest_car.pay_val = pay_val
                guest_car.save()
                context = {
                    'out_time': out_time,
                    'pay_value': pay_balance
                }
                return render(request, 'parking/success_out.html', context)
            else:
                return redirect('parking:index')
    else:  # GET 요청

        try:
            referer = request.META['HTTP_REFERER']  # 레퍼러가 없으면 KeyError 발생
            guest_car = Log.objects.get(car_number=car_number, car_stat=True)
        except ObjectDoesNotExist:
            return render(request, 'parking/404.html', {})
        except KeyError:
            return render(request, 'parking/404.html', {})

        form = CalcForm()
        out_time = guest_car.car_out
        in_time = guest_car.car_in
        pay_val = math.ceil((out_time - in_time).seconds / 60) * 100
        context = {
            'car_number': car_number,
            'form': form,
            'pay_balance': pay_val,
        }
        return render(request, 'parking/calc.html', context)


def register(request):
    if request.method == 'POST':

        name = request.POST['name']
        phone = request.POST['phone']
        email = request.POST['email']
        car_num = request.POST['car_num']
        ticket_num = request.POST['ticket_num']
        ticket_limit = request.POST['ticket_limit']

        regex_name = re.compile('^[가-힣a-zA-Z]+$')
        regex_phone = re.compile('^01[016789]-\d{3,4}-\d{4}$')
        regex_car_num = re.compile('\d{2,3}[가-힣]{1}\d{4}$')
        regex_ticket_num = re.compile('^[0-9]{5}$')

        name_check = regex_name.match(name)
        car_check = regex_car_num.match(car_num)
        phone_check = regex_phone.match(phone)
        ticket_check = regex_ticket_num.match(ticket_num)

        if name_check and car_check and phone_check and ticket_check:
            if User.objects.filter(name=name, phone=phone, email=email).exists():
                user = User.objects.get(name=name, phone=phone, email=email)
                user_car_list = Car.objects.filter(user_id=user.id).values_list('car_num', 'ticket_num')
                new_info = (car_num, ticket_num)
                if new_info in user_car_list:  # 기존가입자 무조건갱신
                    car = Car.objects.get(car_num=car_num, ticket_num=ticket_num, user_id=user.pk)
                    car.ticket_limit = ticket_limit
                    car.save()
                    context = {'success': '갱신되었습니다.'}
                    return HttpResponse(json.dumps(context), content_type='application/json')
                else:  # (차번호, 티켓번호) 불일치
                    if ticket_num in Car.objects.all().values_list('ticket_num',
                                                                   flat=True):  # 차번호 불일치 티켓번호 일치 = > 중복되는 티켓이 존재합니다
                        context = {'message': '중복되는 티켓이 존재합니다'}
                        return HttpResponse(json.dumps(context), content_type='application/json')
                    else:
                        if car_num in Car.objects.all().values_list('car_num',
                                                                    flat=True):  # 차번호 일치 티켓번호 불일치  = >  이미 등록된 티켓번호 입니다.
                            context = {'message': '이미 등록된 티켓이 있습니다.'}
                            return HttpResponse(json.dumps(context), content_type='application/json')
                        else:  # 둘다 불일치 => 기존유저가 새로운차 등록
                            car = Car(car_num=car_num, ticket_num=ticket_num, ticket_limit=ticket_limit, user_id=user.pk)
                            car.save()
                            context = {'success': '새로운 차량 추가'}
                            return HttpResponse(json.dumps(context), content_type='application/json')
            else:  # 완전 신규등록
                print(8)
                user = User(name=name, phone=phone, email=email)
                user.save()
                car = Car(car_num=car_num, ticket_num=ticket_num, ticket_limit=ticket_limit, user_id=user.pk)
                car.save()
                context = {'success': '신규등록'}
                return HttpResponse(json.dumps(context), content_type='application/json')
        else:  # 입력값 오류
            print(9)
            context = {'message': '입력 형식이 잘못되엇습니다.'}
            return HttpResponse(json.dumps(context), content_type='application/json')
    else:
        return render(request, 'parking/wrong_request.html', {})
