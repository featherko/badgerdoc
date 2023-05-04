from pathlib import Path
from typing import List

from .minio_utils import MinioCommunicator
from .schemas import AnnotationFromS3, ClassifierRequest, PageDOD


def put_annotation(
    loader: MinioCommunicator,
    work_dir: Path,
    annotation: List[PageDOD],
    request: ClassifierRequest,
) -> None:
    """Put an annotation to s3-storage."""
    updated_annotation_path = Path(work_dir) / f"out_{request.input_path.name}"

    output_annotation = AnnotationFromS3(**annotation).json(by_alias=True)
    updated_annotation_path.write_text(output_annotation)
    if not loader.client.bucket_exists(f"{request.output_bucket}"):
        loader.client.make_bucket(f"{request.output_bucket}")
    loader.client.fput_object(
        request.output_bucket,
        str(request.output_path),
        str(updated_annotation_path),
    )
