import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource

def setup_telemetry(app_name: str):
    resource = Resource.create({"service.name": app_name})
    provider = TracerProvider(resource=resource)
    
    # Export to console
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    
    trace.set_tracer_provider(provider)
    print(f"Telemetry setup complete for {app_name}")
