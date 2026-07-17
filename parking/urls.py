from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/',                 views.dashboard,      name='dashboard'),
    path('search/',                    views.search_parking, name='search'),
    path('lot/<int:lot_id>/',          views.lot_detail,     name='lot_detail'),
    path('book/',                      views.book_slot,      name='book_slot'),
    path('bookings/',                  views.my_bookings,    name='my_bookings'),
    path('cancel/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),

    # Admin dashboard
    path('manage/',                  views.manage_dashboard, name='manage_dashboard'),
    path('manage/add-lot/',          views.add_lot,          name='add_lot'),
    path('manage/<int:lot_id>/add-slots/', views.add_slots,  name='add_slots'),
]
