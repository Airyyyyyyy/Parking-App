import json
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from parking.models import ParkingLot
from .ml_engine import ParkingMLEngine

_engine = ParkingMLEngine()


@login_required
def trends(request):
    """
    Simple analytics dashboard: peak hours and availability trends for a
    selected parking lot (defaults to the first open lot).
    """
    lots = list(ParkingLot.objects.filter(status='open').values('id', 'name'))

    selected_id = request.GET.get('lot')
    selected = None
    if selected_id:
        selected = next((l for l in lots if str(l['id']) == str(selected_id)), None)
    if selected is None and lots:
        selected = lots[0]

    context = {'lots': lots, 'selected': selected}
    if selected:
        lot_id = selected['id']
        context['hourly_data']     = json.dumps(_engine.hourly_averages(lot_id))
        context['recommendations'] = _engine.get_recommendations(lot_id)

    return render(request, 'analytics/trends.html', context)
