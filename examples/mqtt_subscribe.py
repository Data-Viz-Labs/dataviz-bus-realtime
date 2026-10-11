"""Subscribe to the live bus feed over MQTT/WebSockets and print one line per message.

    pip install paho-mqtt        # >= 2.0
    export MQTT_ENDPOINT=abc123-ats.iot.eu-west-1.amazonaws.com   # terraform output mqtt_endpoint
    export MQTT_AUTHORIZER=madrid-bus-groups                         # terraform output mqtt_authorizer_name
    export API_KEY=<your group key>
    python examples/mqtt_subscribe.py --line 27      # or --line + for every line

Topics and payloads: docs/api/asyncapi.yaml.
"""

import argparse
import json
import os
from urllib.parse import urlencode
import uuid

import paho.mqtt.client as mqtt


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        raise SystemExit(f"connection refused: {reason_code} (check MQTT_AUTHORIZER and API_KEY)")
    topic = f"madrid/lines/{userdata}/#"
    client.subscribe(topic, qos=0)
    print(f"subscribed to {topic}")


def on_message(client, userdata, msg):
    data = json.loads(msg.payload)
    if msg.topic.endswith("/state"):
        buses = data["buses"]
        load = sum(b["load"] for b in buses) / len(buses) if buses else 0
        print(f"{data['time'][11:19]} line {data['line_id']:>4} state: {len(buses)} buses, "
              f"mean load {load:.0%}, {sum(data['waiting'].values())} waiting")
    else:
        for c in data["calls"]:
            print(f"{c['time'][11:19]} line {data['line_id']:>4} {c['bus_id']} at {c['stop_id']}: "
                  f"-{c['alighted']} +{c['boarded']} = {c['passengers_after']}"
                  + (f" ({c['left_behind']} left behind)" if c["left_behind"] else ""))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--endpoint", default=os.environ.get("MQTT_ENDPOINT"))
    parser.add_argument("--authorizer", default=os.environ.get("MQTT_AUTHORIZER"))
    parser.add_argument("--key", default=os.environ.get("API_KEY"))
    parser.add_argument("--line", default=os.environ.get("LINE", "27"), help="line id, or + for all lines")
    args = parser.parse_args()
    if not (args.endpoint and args.authorizer and args.key):
        parser.error("set MQTT_ENDPOINT, MQTT_AUTHORIZER and API_KEY (or --endpoint/--authorizer/--key)")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"student-{uuid.uuid4().hex[:8]}",
                         transport="websockets", userdata=args.line)
    client.ws_set_options(path="/mqtt?" + urlencode({"x-amz-customauthorizer-name": args.authorizer,
                                                     "token": args.key}))
    client.tls_set()
    client.on_connect, client.on_message = on_connect, on_message
    client.connect(args.endpoint, 443, keepalive=60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        client.disconnect()


if __name__ == "__main__":
    main()
