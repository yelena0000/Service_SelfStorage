from django.shortcuts import render
from .models import Client

def display_statistics(request):
    stats = Client.get_statistics()
    return render(request, 'admin/statistics_change_list.html', {'stats': stats})