"""통합 시험의 주차 단계가 끝나면 카메라를 유지하고 주차 HTTP만 차단합니다."""
from contextlib import contextmanager
from pathlib import Path
import threading


@contextmanager
def parking_delivery_gate(root):
    from ai_vision.recognition.vehicle_http import VehicleHTTPClient
    from ai_vision.parking.parking_delivery import ParkingDelivery, ParkingDeliveryWorker
    root=Path(root);flag=root/'parking_delivery_paused.flag'
    lock=threading.RLock()
    enabled=VehicleHTTPClient.enabled
    vehicle_send=VehicleHTTPClient.send
    occupancy_send=ParkingDelivery.send
    worker_poll=ParkingDeliveryWorker.poll
    worker_enqueue=ParkingDeliveryWorker.enqueue

    def send_vehicle(client,payload):
        with lock:return vehicle_send(client,payload)

    def send_occupancy(client,event):
        with lock:
            if flag.exists():
                return {'event_id':event['event_id'],'status':'CANCELLED_BEFORE_SEND',
                        'reason':'PARKING_PHASE_COMPLETE'}
            return occupancy_send(client,event)

    def poll(worker,persist):
        value=worker_poll(worker,persist)
        if flag.exists() and worker.pending==0 and not worker.blocked:
            with lock:(root/'parking_delivery_paused.parking.ack').touch()
        return value

    def enqueue(worker,event,receipt):
        if flag.exists() and not worker.closed and not worker.blocked:
            receipt.update(status='CANCELLED_BEFORE_SEND',reason='PARKING_PHASE_COMPLETE')
            return True
        return worker_enqueue(worker,event,receipt)

    def acknowledge_gate():
        if flag.exists():
            with lock:(root/'parking_delivery_paused.gate.ack').touch()

    # 1. 기본 OFF 상태로 반환하여 기존 흐름이 미전송 결과를 정상 구분하게 합니다.
    VehicleHTTPClient.enabled=property(lambda client:enabled.fget(client) and not flag.exists())
    VehicleHTTPClient.send=send_vehicle
    ParkingDelivery.send=send_occupancy
    ParkingDeliveryWorker.poll=poll
    ParkingDeliveryWorker.enqueue=enqueue
    try:yield acknowledge_gate
    finally:
        VehicleHTTPClient.enabled=enabled
        VehicleHTTPClient.send=vehicle_send
        ParkingDelivery.send=occupancy_send
        ParkingDeliveryWorker.poll=worker_poll
        ParkingDeliveryWorker.enqueue=worker_enqueue
