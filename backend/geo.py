import json
import math
from pathlib import Path

CAMPUS=json.loads((Path(__file__).resolve().parents[1]/'shared/campus.json').read_text(encoding='utf-8'))
LANDMARKS=CAMPUS['landmarks']


def distance_m(lat1,lng1,lat2,lng2):
    p1,p2=math.radians(lat1),math.radians(lat2)
    a=math.sin((p2-p1)/2)**2+math.cos(p1)*math.cos(p2)*math.sin(math.radians(lng2-lng1)/2)**2
    return 6371000*2*math.asin(math.sqrt(min(1,a)))


def in_demo_area(lat,lng):
    (south,west),(north,east)=CAMPUS['bounds']
    return math.isfinite(lat) and math.isfinite(lng) and south<=lat<=north and west<=lng<=east


def nearest(lat,lng):
    return min(LANDMARKS,key=lambda l:distance_m(lat,lng,l['lat'],l['lng']))


def pin_label(pin):
    landmark=nearest(pin['lat'],pin['lng'])
    return f"Near {landmark['name']}" if distance_m(pin['lat'],pin['lng'],landmark['lat'],landmark['lng'])<=200 else 'Pinned campus location'
