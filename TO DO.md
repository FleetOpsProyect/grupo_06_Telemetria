# HU-04 / FLEET-3 — Plan de viaje por SNS/SQS

## Propuesta para compartir con Asignaciones

Publicar el origen, el destino y la duración estimada, asociados al `asignacion_id`,
al planificar o iniciar el viaje. Telemetría recibe el plan por SNS/SQS y lo
persiste localmente. Al recibir una interrupción, busca la ruta activa por
`asignacion_id` y estima la distancia parcial sin consultar a otro servicio.

Una vez cerrada como `INTERRUMPIDA`, la ruta genera un `RutaFinalizadaEvent`
para que Vehículos actualice el odómetro. La distancia es una estimación en
línea geodésica, no una medición GPS ni distancia efectiva por carretera.

## Contrato provisional para simular el productor

```json
{
  "evento_id": "70b8730c-b576-4a91-af49-830f1388c92d",
  "tipo_evento": "PlanViajeAsignacionEvent",
  "version": "1.0",
  "fecha_evento": "2026-10-05T08:00:00Z",
  "origen": "asignaciones",
  "datos": {
    "asignacion_id": "asig-8472",
    "coordenada_origen": {"latitud": 0.0, "longitud": 0.0},
    "coordenada_destino": {"latitud": 0.0, "longitud": 0.2},
    "duracion_estimada_segundos": 1800
  }
}
```

- Este contrato admite un plan inicial por asignación; no simula revisiones.
- El evento de interrupción sigue requiriendo solamente `asignacion_id` en `datos`.
- Con ruta activa y sin plan, no se guarda el cierre ni se marca la interrupción
  como procesada. Se devuelve un error recuperable para intentar más tarde.
- El cierre usa la hora de procesamiento, según el criterio actual de Jira.

## Simular localmente

Con las dependencias de desarrollo instaladas, ejecutar:

```sh
python -m pytest -q tests/integration/test_assignment_message_flow.py
```

La prueba entrega el plan y la interrupción como sobres JSON a
`handle_assignment_message`, calcula ~11,12 km y comprueba que el outbox tiene
un solo evento aunque la cola vuelva a entregar la interrupción. El futuro
consumidor SQS puede pasar el cuerpo de dominio a esa misma función; si SNS
envuelve el JSON, debe extraerlo primero.

## Pendiente antes de conectar AWS

- [ ] Confirmar productor, nombre del evento, campos y tratamiento de revisiones.
- [ ] Confirmar si se mantiene la hora de procesamiento o se adopta la hora del
  incidente; una entrega tardía puede alterar el kilometraje estimado.
- [ ] Configurar el tópico SNS, la cola SQS, sus filtros y la DLQ; conectar el
  consumidor y el publicador del outbox. No borrar el mensaje antes del commit.
- [ ] Definir límite de espera por un plan que llega fuera de orden y política
  de reintentos/DLQ; no completar silenciosamente con kilómetros inventados.
- [ ] Aplicar el cambio de esquema y verificar la concurrencia en PostgreSQL.
