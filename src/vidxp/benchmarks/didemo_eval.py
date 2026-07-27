from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PRINT_REPLACEMENTS = {
    'print "Average rank@1: %f" %rank1':
        'print("Average rank@1: %f" %rank1)',
    'print "Average rank@5: %f" %rank5':
        'print("Average rank@5: %f" %rank5)',
    'print "Average iou: %f" %miou':
        'print("Average iou: %f" %miou)',
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluator", required=True)
    parser.add_argument("--annotations", required=True)
    parser.add_argument("--predictions", required=True)
    options = parser.parse_args()

    evaluator = Path(options.evaluator).resolve()
    source = evaluator.read_text(encoding="utf-8")
    for original, compatible in PRINT_REPLACEMENTS.items():
        if source.count(original) != 1:
            raise RuntimeError(
                "Pinned DiDeMo evaluator no longer matches the expected "
                "three Python 2 print statements."
            )
        source = source.replace(original, compatible)

    sys.path.insert(0, str(evaluator.parent))
    namespace = {
        "__file__": str(evaluator),
        "__name__": "vidxp_official_didemo_evaluator",
    }
    exec(compile(source, str(evaluator), "exec"), namespace)

    annotations = json.loads(
        Path(options.annotations).read_text(encoding="utf-8")
    )
    serialized = json.loads(
        Path(options.predictions).read_text(encoding="utf-8")
    )
    predictions = [
        [tuple(moment) for moment in ranking]
        for ranking in serialized
    ]
    rank1, rank5, mean_iou = namespace["eval_predictions"](
        predictions,
        annotations,
    )
    print(
        "VIDXP_METRICS_JSON="
        + json.dumps(
            {
                "rank_at_1": float(rank1),
                "rank_at_5": float(rank5),
                "mean_iou": float(mean_iou),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
