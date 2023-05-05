import tempfile
from pathlib import Path

from fastapi import APIRouter

from .minio_utils import MinioCommunicator
from .schemas import ClassifierRequest, ClassifierResponse
from .utils import put_annotation

router = APIRouter()


OUTPUT = {
  "text": {
    "1": [
      "a7f17d17-75d5-442f-bd65-cbf484e1c9d9",
      "2aefd08b-7d47-44d7-817e-f4e043301999",
      "65ee9896-aa54-4c14-90b3-9014875a3134",
      "3b5bea2d-4b2f-4263-880e-ab12071f426d",
      "07ce7ace-1cdf-4e56-a96e-4a4bc16ce7bc"
    ]
  }
}

SOMETHING = {
  "pages": [
    {
      "page_num": 1,
      "size": {
        "width": 595.304,
        "height": 841.89
      },
      "objs": [
        {
          "id": "a7f17d17-75d5-442f-bd65-cbf484e1c9d9",
          "bbox": [
            65.52,
            347.04,
            511.92,
            391.92
          ],
          "category": "text"
        },
        {
          "id": "2aefd08b-7d47-44d7-817e-f4e043301999",
          "bbox": [
            65.52,
            184.56,
            502.56,
            246.24
          ],
          "category": "text"
        },
        {
          "id": "65ee9896-aa54-4c14-90b3-9014875a3134",
          "bbox": [
            66.48,
            265.92,
            501.6,
            327.84
          ],
          "category": "text"
        },
        {
          "id": "3b5bea2d-4b2f-4263-880e-ab12071f426d",
          "bbox": [
            64.56,
            122.64,
            502.8,
            165.12
          ],
          "category": "text"
        },
        {
          "id": "07ce7ace-1cdf-4e56-a96e-4a4bc16ce7bc",
          "bbox": [
            68.88,
            57.84,
            509.04,
            103.92
          ],
          "category": "text"
        }
      ]
    }
  ]
}


@router.post("/test")
def predict(request: ClassifierRequest):
    with tempfile.TemporaryDirectory() as tmpdirname:
        loader = MinioCommunicator()
        put_annotation(loader, Path(tmpdirname), SOMETHING, request)
    return ClassifierResponse(__root__=OUTPUT)
