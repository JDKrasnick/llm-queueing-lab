import argparse
from pathlib import Path
import json

from .model import Catalog, Config, RequestClass
from .provenance import write_json


def main():
    parser = argparse.ArgumentParser(description="Queueing-network research with an actual-engine adapter")
    commands = parser.add_subparsers(dest="command",required=True)
    screen = commands.add_parser("screen",help="Run the complete predeclared synthetic screen")
    screen.add_argument("--output",required=True)
    screen.add_argument("--horizon",type=float,default=30)
    report = commands.add_parser("report",help="Render all-cell tables and scientific figures")
    report.add_argument("directory")
    capacity = commands.add_parser("capacity",help="Exact model capacity certificate")
    capacity.add_argument("--config")
    hardware_config = commands.add_parser("hardware-config",help="Write the small two-class GPU configuration")
    hardware_config.add_argument("output")
    calibration = commands.add_parser("calibrate",help="Measure every gated action on the actual Engine")
    calibration.add_argument("--config",required=True)
    calibration.add_argument("--model",required=True)
    calibration.add_argument("--output",required=True)
    calibration.add_argument("--reps",type=int,default=3)
    calibration.add_argument("--provider",default="cuda")
    hardware = commands.add_parser("hardware",help="One fixed-horizon actual Engine experiment")
    hardware.add_argument("--model",required=True)
    hardware.add_argument("--table",required=True)
    hardware.add_argument("--output",required=True)
    hardware.add_argument("--policy",choices=("native","fcfs","pressure"),required=True)
    hardware.add_argument("--rate",type=float,required=True)
    hardware.add_argument("--horizon",type=float,default=20)
    hardware.add_argument("--seed",type=int,required=True)
    hardware.add_argument("--provider",default="cuda")
    hardware.add_argument("--pattern",choices=("poisson","bursty","phase"),default="poisson")
    args = parser.parse_args()
    if args.command == "screen":
        from .experiments import run_screen
        print(json.dumps(run_screen(args.output,args.horizon),indent=2))
    elif args.command == "report":
        from .report import render
        render(args.directory)
    elif args.command == "capacity":
        config = Config.from_dict(json.loads(Path(args.config).read_text())) if args.config else Config()
        catalog = Catalog(config)
        print(json.dumps(dict(catalog.capacity((0.5,0.5)),monotone=catalog.monotone()),indent=2))
    elif args.command == "hardware-config":
        config = Config(classes=(RequestClass("prefill",769,16,32),RequestClass("decode",65,96,128)),
                        rows=4,blocks=16,block_size=256)
        write_json(args.output,config.as_dict())
    elif args.command == "calibrate":
        from .hardware import calibrate
        calibrate(args.model,Config.from_dict(json.loads(Path(args.config).read_text())),args.output,args.reps,args.provider)
    else:
        from .hardware import run_hardware
        print(json.dumps(run_hardware(args.model,args.table,args.output,args.policy,args.rate,args.horizon,args.seed,args.provider,args.pattern),indent=2))

