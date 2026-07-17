import json
from functools import wraps
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import ParkingLot, ParkingSlot, Booking, OccupancyRecord
from analytics.ml_engine import ParkingMLEngine

_engine = ParkingMLEngine()


def admin_required(view_func):
    """Allow only admin-role (or staff) users through; others get 403."""
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if getattr(request.user, 'role', None) != 'admin' and not request.user.is_staff:
            return HttpResponseForbidden('Admins only.')
        return view_func(request, *args, **kwargs)
    return _wrapped


def _record_occupancy(lot):
    """Snapshot a lot's current occupancy for the ML training history."""
    now = timezone.now()
    OccupancyRecord.objects.create(
        lot=lot,
        occupancy_percentage=lot.occupancy_percentage(),
        day_of_week=now.weekday(),
        hour_of_day=now.hour,
        is_weekend=now.weekday() >= 5,
    )


def _reset_daily_bookings():
    """
    Expire confirmed bookings from previous days.
    Runs lazily on the first request of each new day — no scheduler needed.
    """
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    old_bookings = list(
        Booking.objects.filter(status='confirmed', booked_at__lt=today_start)
        .values('id', 'slot_id')
    )
    if not old_bookings:
        return

    affected_lot_ids = set()
    for b in old_bookings:
        slot = ParkingSlot.objects.filter(id=b['slot_id']).first()
        if slot and slot.status == 'occupied':
            slot.status = 'available'
            slot.save()
            affected_lot_ids.add(slot.lot_id)
        bk = Booking.objects.filter(id=b['id']).first()
        if bk:
            bk.status = 'completed'
            bk.save()

    for lot_id in affected_lot_ids:
        lot = ParkingLot.objects.filter(id=lot_id).first()
        if lot:
            avail = list(ParkingSlot.objects.filter(lot_id=lot_id, status='available').values('id'))
            lot.available_slots = len(avail)
            lot.save()
            _record_occupancy(lot)


@login_required
def search_parking(request):
    _reset_daily_bookings()
    all_lots = list(ParkingLot.objects.filter(status='open').values(
        'id', 'name', 'address',
        'available_slots', 'total_slots',
    ))

    location = request.GET.get('location', request.GET.get('q', '')).strip()
    if location:
        loc_lower = location.lower()
        result = [
            l for l in all_lots
            if loc_lower in l['name'].lower() or loc_lower in l['address'].lower()
        ]
        return JsonResponse(result, safe=False)

    return render(request, 'parking/search.html', {'lots': all_lots})


@login_required
def lot_detail(request, lot_id):
    _reset_daily_bookings()
    lot          = get_object_or_404(ParkingLot, id=lot_id)
    prediction   = _engine.predict_availability(lot_id)
    hourly_data  = _engine.hourly_averages(lot_id)
    recommendations = _engine.get_recommendations(lot_id)

    return render(request, 'parking/lot_detail.html', {
        'lot':             lot,
        'prediction':      prediction,
        'hourly_data':     json.dumps(hourly_data),
        'recommendations': recommendations,
    })


@login_required
@require_POST
def book_slot(request):
    _reset_daily_bookings()
    data   = json.loads(request.body)
    lot_id = data.get('lot_id')

    lot  = ParkingLot.objects.filter(id=lot_id, status='open').first()
    if lot is None:
        return JsonResponse({'error': 'Lot not found or closed.'}, status=404)

    slot = ParkingSlot.objects.filter(lot=lot, status='available').first()
    if slot is None:
        return JsonResponse({'error': 'No available slots in this lot.'}, status=400)

    Booking.objects.create(user=request.user, slot=slot, status='confirmed')
    slot.status = 'occupied'
    slot.save()
    lot.available_slots = max(0, lot.available_slots - 1)
    lot.save()

    _record_occupancy(lot)
    return JsonResponse({'success': True, 'slot_number': slot.slot_number})


@login_required
def dashboard(request):
    _reset_daily_bookings()
    raw = list(Booking.objects.filter(user=request.user).values(
        'id', 'status', 'booked_at', 'slot_id'
    ))

    total     = len(raw)
    confirmed = len([b for b in raw if b['status'] == 'confirmed'])
    completed = len([b for b in raw if b['status'] == 'completed'])
    cancelled = len([b for b in raw if b['status'] == 'cancelled'])

    recent = []
    for b in sorted(raw, key=lambda x: x['booked_at'], reverse=True)[:3]:
        slot = ParkingSlot.objects.filter(id=b['slot_id']).first()
        if slot:
            lot = ParkingLot.objects.filter(id=slot.lot_id).first()
            recent.append({
                'id':          b['id'],
                'status':      b['status'],
                'booked_at':   b['booked_at'],
                'slot_number': slot.slot_number,
                'lot_name':    lot.name if lot else 'Unknown',
                'lot_id':      slot.lot_id,
            })

    return render(request, 'parking/dashboard.html', {
        'stats': {
            'total':     total,
            'confirmed': confirmed,
            'completed': completed,
            'cancelled': cancelled,
        },
        'recent_bookings': recent,
    })


@login_required
def my_bookings(request):
    raw = list(Booking.objects.filter(user=request.user).values(
        'id', 'status', 'booked_at', 'slot_id'
    ))
    bookings = []
    for b in raw:
        slot = ParkingSlot.objects.filter(id=b['slot_id']).first()
        if slot:
            lot = ParkingLot.objects.filter(id=slot.lot_id).first()
            bookings.append({
                'id':          b['id'],
                'status':      b['status'],
                'booked_at':   b['booked_at'],
                'slot_number': slot.slot_number,
                'lot_name':    lot.name if lot else 'Unknown',
                'lot_id':      slot.lot_id,
            })
    return render(request, 'parking/bookings.html', {'bookings': bookings})


@login_required
@require_POST
def cancel_booking(request, booking_id):
    booking = Booking.objects.filter(id=booking_id, user=request.user).first()
    if booking is None:
        return JsonResponse({'error': 'Booking not found.'}, status=404)
    if booking.status != 'confirmed':
        return JsonResponse({'error': 'Only confirmed bookings can be cancelled.'}, status=400)

    booking.status = 'cancelled'
    booking.save()

    slot = ParkingSlot.objects.filter(id=booking.slot_id).first()
    if slot:
        slot.status = 'available'
        slot.save()
        lot = ParkingLot.objects.filter(id=slot.lot_id).first()
        if lot:
            lot.available_slots += 1
            lot.save()
            _record_occupancy(lot)

    return JsonResponse({'success': True})


# ── Admin dashboard (add / manage parking lots and slots) ──────────────────

@admin_required
def manage_dashboard(request):
    lots = []
    for lot in ParkingLot.objects.all():
        lots.append({
            'id':          lot.id,
            'name':        lot.name,
            'address':     lot.address,
            'total_slots': lot.total_slots,
            'available':   lot.available_slots,
            'occupancy':   round(lot.occupancy_percentage()),
            'status':      lot.status,
        })
    return render(request, 'parking/manage_dashboard.html', {'lots': lots})


@admin_required
def add_lot(request):
    if request.method == 'POST':
        name    = request.POST.get('name', '').strip()
        address = request.POST.get('address', '').strip()
        lat     = request.POST.get('latitude', '').strip()
        lng     = request.POST.get('longitude', '').strip()
        total   = request.POST.get('total_slots', '').strip()

        error = None
        if not name:
            error = 'Lot name is required.'
        elif not address:
            error = 'Address is required.'
        elif not total.isdigit() or int(total) < 1:
            error = 'Total slots must be a positive whole number.'
        elif ParkingLot.objects.filter(name=name).first() is not None:
            error = 'A parking lot with that name already exists.'

        if error:
            return render(request, 'parking/manage_lot_form.html', {
                'error': error, 'form': request.POST,
            })

        total = int(total)
        lot = ParkingLot.objects.create(
            name=name,
            address=address,
            latitude=float(lat) if lat else None,
            longitude=float(lng) if lng else None,
            total_slots=total,
            available_slots=total,
            admin=request.user,
        )
        # Auto-create the slots for this lot.
        ParkingSlot.objects.bulk_create([
            ParkingSlot(lot=lot, slot_number=f"S{i:03d}", status='available')
            for i in range(1, total + 1)
        ])
        messages.success(request, f'Created "{lot.name}" with {total} slots.')
        return redirect('manage_dashboard')

    return render(request, 'parking/manage_lot_form.html')


@admin_required
@require_POST
def add_slots(request, lot_id):
    lot = get_object_or_404(ParkingLot, id=lot_id)
    count = request.POST.get('count', '').strip()
    if not count.isdigit() or int(count) < 1:
        messages.error(request, 'Enter a positive number of slots to add.')
        return redirect('manage_dashboard')

    count = int(count)
    existing = lot.total_slots
    ParkingSlot.objects.bulk_create([
        ParkingSlot(lot=lot, slot_number=f"S{i:03d}", status='available')
        for i in range(existing + 1, existing + count + 1)
    ])
    lot.total_slots     += count
    lot.available_slots += count
    lot.save()
    messages.success(request, f'Added {count} slots to "{lot.name}".')
    return redirect('manage_dashboard')
