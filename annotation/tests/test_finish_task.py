import copy
import os
import uuid
from unittest.mock import Mock, patch

import pytest
import responses
from fastapi.testclient import TestClient
from requests.exceptions import ConnectionError, RequestException, Timeout
from sqlalchemy import asc, not_
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from annotation.annotations import accumulate_pages_info, row_to_dict
from annotation.models import (
    AgreementMetrics,
    AnnotatedDoc,
    Category,
    File,
    Job,
    ManualAnnotationTask,
    User,
)
from annotation.schemas import (
    AgreementScoreServiceResponse,
    CategoryTypeSchema,
    FileStatusEnumSchema,
    JobStatusEnumSchema,
    TaskStatusEnumSchema,
    ValidationSchema,
)
from annotation.tasks import get_task_revisions
from tests.consts import FINISH_TASK_PATH
from tests.override_app_dependency import TEST_HEADERS, TEST_TENANT, app

client = TestClient(app)

CATEGORIES = [
    Category(
        id="18d3d189e73a4680bfa77ba3fe6ebee5",
        name="Test",
        type=CategoryTypeSchema.box,
    )
]
CATEGORIES_2 = [
    Category(
        id="1234",
        name="Test",
        type=CategoryTypeSchema.box,
    )
]
FINISH_TASK_USER_1 = User(user_id="17ec1df0-006d-4905-a902-fbd1ed99a49d")
FINISH_TASK_USER_2 = User(user_id="23ec1df0-006d-4905-a902-fbd1ed99a49d")
FINISH_TASK_USER_3 = User(user_id="31ec1df0-006d-4905-a902-fbd1ed99a49d")
VALIDATION_TYPE = "cross"

FINISH_TASK_FILE_1 = File(
    file_id=1,
    tenant=TEST_TENANT,
    job_id=1,
    pages_number=9,
    distributed_annotating_pages=[1, 2, 3, 4, 5, 6, 7, 8, 9],
    annotated_pages=[1, 2, 3, 4, 5, 6, 7, 8, 9],
    distributed_validating_pages=[1, 2, 3, 4, 5, 6, 7, 8, 9],
    validated_pages=[1, 2, 3, 4, 5, 6],
    status=FileStatusEnumSchema.annotated,
)
FINISH_TASK_FILE_2 = File(
    file_id=2,
    tenant=TEST_TENANT,
    job_id=2,
    pages_number=9,
)

FINISH_TASK_FILE_3 = File(
    file_id=3,
    tenant=TEST_TENANT,
    job_id=3,
    pages_number=9,
    annotated_pages=[1, 2, 3, 4, 5],
    status=FileStatusEnumSchema.pending,
)
FINISH_TASK_FILE_4 = File(
    file_id=4,
    tenant=TEST_TENANT,
    job_id=4,
    pages_number=4,
)

FINISH_TASK_JOB_1 = Job(
    job_id=1,
    callback_url="http://www.test.com/test1",
    annotators=[FINISH_TASK_USER_1],
    validation_type=ValidationSchema.cross,
    files=[FINISH_TASK_FILE_1],
    is_auto_distribution=False,
    categories=CATEGORIES,
    deadline=None,
    tenant=TEST_TENANT,
    status=JobStatusEnumSchema.in_progress,
)
FINISH_TASK_JOB_2 = Job(
    job_id=2,
    callback_url="http://www.test.com/test1",
    annotators=[FINISH_TASK_USER_1],
    validation_type=ValidationSchema.cross,
    files=[FINISH_TASK_FILE_2],
    is_auto_distribution=False,
    categories=CATEGORIES,
    deadline=None,
    tenant=TEST_TENANT,
)
FINISH_TASK_JOB_3 = Job(
    job_id=3,
    callback_url="http://www.test.com/test1",
    annotators=[FINISH_TASK_USER_1],
    validators=[FINISH_TASK_USER_1],
    validation_type=ValidationSchema.hierarchical,
    files=[FINISH_TASK_FILE_3],
    is_auto_distribution=False,
    categories=CATEGORIES,
    deadline=None,
    tenant=TEST_TENANT,
)
FINISH_TASK_JOB_4 = Job(
    job_id=4,
    callback_url="http://www.test.com/test1",
    annotators=[FINISH_TASK_USER_1, FINISH_TASK_USER_2],
    validators=[FINISH_TASK_USER_3],
    validation_type=ValidationSchema.hierarchical,
    files=[FINISH_TASK_FILE_4],
    is_auto_distribution=False,
    categories=CATEGORIES,
    deadline=None,
    tenant=TEST_TENANT,
)
FINISH_TASK_1 = {
    "id": 1,
    "file_id": FINISH_TASK_FILE_1.file_id,
    "pages": [1, 2, 3, 4, 5, 6, 7, 8, 9],
    "job_id": FINISH_TASK_JOB_1.job_id,
    "user_id": FINISH_TASK_USER_1.user_id,
    "is_validation": False,
    "status": TaskStatusEnumSchema.finished,
    "deadline": None,
}
FINISH_TASK_2 = {
    "id": 2,
    "file_id": FINISH_TASK_FILE_1.file_id,
    "pages": [1, 2, 3, 4, 5, 6],
    "job_id": FINISH_TASK_JOB_1.job_id,
    "user_id": FINISH_TASK_USER_1.user_id,
    "is_validation": True,
    "status": TaskStatusEnumSchema.finished,
    "deadline": None,
}
FINISH_TASK_1_SAME_JOB = {
    "id": 3,
    "file_id": FINISH_TASK_FILE_1.file_id,
    "pages": [8, 9, 7],
    "job_id": FINISH_TASK_JOB_1.job_id,
    "user_id": FINISH_TASK_USER_1.user_id,
    "is_validation": True,
    "status": TaskStatusEnumSchema.in_progress,
    "deadline": None,
}
FINISH_TASK_2_SAME_JOB = {
    "id": 4,
    "file_id": FINISH_TASK_FILE_1.file_id,
    "pages": [1],
    "job_id": FINISH_TASK_JOB_1.job_id,
    "user_id": FINISH_TASK_USER_1.user_id,
    "is_validation": True,
    "status": TaskStatusEnumSchema.in_progress,
    "deadline": None,
}
FINISH_TASK_ID = FINISH_TASK_1_SAME_JOB["id"]
NOT_EXISTING_ID = 6
BAD_ID = "bad_id"

FINISH_UPDATED_TASK = copy.deepcopy(FINISH_TASK_1_SAME_JOB)
FINISH_UPDATED_TASK["status"] = TaskStatusEnumSchema.finished

TASK_NOT_IN_PROGRESS_STATUS = {
    "id": 5,
    "file_id": FINISH_TASK_FILE_1.file_id,
    "pages": [1],
    "job_id": FINISH_TASK_JOB_2.job_id,
    "user_id": FINISH_TASK_USER_1.user_id,
    "is_validation": True,
    "status": TaskStatusEnumSchema.pending,
    "deadline": None,
}
FINISH_TASK_CHECK_DELETE_USER_ANNOTATOR_1 = {
    "id": 6,
    "file_id": FINISH_TASK_FILE_4.file_id,
    "pages": [1, 2],
    "job_id": FINISH_TASK_JOB_4.job_id,
    "user_id": FINISH_TASK_USER_1.user_id,
    "is_validation": False,
    "status": TaskStatusEnumSchema.finished,
    "deadline": None,
}
FINISH_TASK_CHECK_DELETE_USER_ANNOTATOR_2 = {
    "id": 7,
    "file_id": FINISH_TASK_FILE_4.file_id,
    "pages": [3, 4],
    "job_id": FINISH_TASK_JOB_4.job_id,
    "user_id": FINISH_TASK_USER_2.user_id,
    "is_validation": False,
    "status": TaskStatusEnumSchema.finished,
    "deadline": None,
}
FINISH_TASK_CHECK_DELETE_USER_VALIDATOR = {
    "id": 8,
    "file_id": FINISH_TASK_FILE_4.file_id,
    "pages": [1, 2, 3, 4],
    "job_id": FINISH_TASK_JOB_4.job_id,
    "user_id": FINISH_TASK_USER_3.user_id,
    "is_validation": True,
    "status": TaskStatusEnumSchema.in_progress,
    "deadline": None,
}
FINISH_DOCS = [
    AnnotatedDoc(
        revision="1",
        user=FINISH_UPDATED_TASK["user_id"],
        pipeline=None,
        file_id=FINISH_UPDATED_TASK["file_id"],
        job_id=FINISH_UPDATED_TASK["job_id"],
        pages={},
        validated=[1, 2, 3, 4, 5, 6, 7, 8, 9],
        failed_validation_pages=[],
        tenant=TEST_TENANT,
        task_id=FINISH_UPDATED_TASK["id"],
        date="2004-10-19T10:01:00",
    ),
    AnnotatedDoc(
        revision="2",
        user=FINISH_TASK_2["user_id"],
        pipeline=None,
        file_id=FINISH_TASK_2["file_id"],
        job_id=FINISH_TASK_2["job_id"],
        pages={},
        validated=[1, 2, 3, 4, 5, 6],
        failed_validation_pages=[],
        tenant=TEST_TENANT,
        task_id=FINISH_TASK_2["id"],
        date="2004-10-19T10:01:00",
    ),
]
FINISH_DOCS_CHECK_DELETED_ANNOTATOR = [
    AnnotatedDoc(
        revision="3",
        user=FINISH_TASK_CHECK_DELETE_USER_ANNOTATOR_1["user_id"],
        pipeline=None,
        file_id=FINISH_TASK_CHECK_DELETE_USER_ANNOTATOR_1["file_id"],
        job_id=FINISH_TASK_CHECK_DELETE_USER_ANNOTATOR_1["job_id"],
        pages={"1": "1", "2": "2"},
        validated=[],
        failed_validation_pages=[],
        tenant=TEST_TENANT,
        task_id=FINISH_TASK_CHECK_DELETE_USER_ANNOTATOR_1["id"],
        date="2004-10-19T10:01:00",
    ),
    AnnotatedDoc(
        revision="4",
        user=FINISH_TASK_CHECK_DELETE_USER_ANNOTATOR_2["user_id"],
        pipeline=None,
        file_id=FINISH_TASK_CHECK_DELETE_USER_ANNOTATOR_2["file_id"],
        job_id=FINISH_TASK_CHECK_DELETE_USER_ANNOTATOR_2["job_id"],
        pages={"3": "3", "4": "4"},
        validated=[],
        failed_validation_pages=[],
        tenant=TEST_TENANT,
        task_id=FINISH_TASK_CHECK_DELETE_USER_ANNOTATOR_2["id"],
        date="2004-10-19T10:01:06",
    ),
    AnnotatedDoc(
        revision="5",
        user=FINISH_TASK_CHECK_DELETE_USER_VALIDATOR["user_id"],
        pipeline=None,
        file_id=FINISH_TASK_CHECK_DELETE_USER_VALIDATOR["file_id"],
        job_id=FINISH_TASK_CHECK_DELETE_USER_VALIDATOR["job_id"],
        pages={},
        validated=[1, 4],
        failed_validation_pages=[2, 3],
        tenant=TEST_TENANT,
        task_id=FINISH_TASK_CHECK_DELETE_USER_VALIDATOR["id"],
        date="2004-10-19T10:01:00",
    ),
]


AGREEMENT_SCORE_RESPONSE = [
    AgreementScoreServiceResponse(
        annotator_id=uuid.uuid4(),
        job_id=1,
        task_id=1,
        agreement_score=[
            {"task_id": 2, "agreement_score": 0.99},
            {"task_id": 3, "agreement_score": 0.81},
            {"task_id": 4, "agreement_score": 0.85},
        ],
    ),
    AgreementScoreServiceResponse(
        annotator_id=uuid.uuid4(),
        job_id=1,
        task_id=2,
        agreement_score=[
            {"task_id": 1, "agreement_score": 0.99},
            {"task_id": 4, "agreement_score": 0.89},
            {"task_id": 3, "agreement_score": 0.86},
        ],
    ),
    AgreementScoreServiceResponse(
        annotator_id=uuid.uuid4(),
        job_id=1,
        task_id=3,
        agreement_score=[
            {"task_id": 4, "agreement_score": 0.92},
            {"task_id": 2, "agreement_score": 0.86},
            {"task_id": 1, "agreement_score": 0.81},
        ],
    ),
    AgreementScoreServiceResponse(
        annotator_id=uuid.uuid4(),
        job_id=1,
        task_id=4,
        agreement_score=[
            {"task_id": 1, "agreement_score": 0.85},
            {"task_id": 2, "agreement_score": 0.89},
            {"task_id": 3, "agreement_score": 0.92},
        ],
    ),
]


def check_files_finished_pages(
    test_session: Session, job_id: int, tenant: str
):
    finished_tasks = test_session.query(ManualAnnotationTask).filter(
        ManualAnnotationTask.job_id == job_id,
        ManualAnnotationTask.status == TaskStatusEnumSchema.finished,
    )
    files = test_session.query(File).filter(File.job_id == job_id).all()
    validation_type = (
        test_session.query(Job.validation_type)
        .filter_by(job_id=job_id)
        .first()
    )

    for task_file in files:
        finished_annotating_tasks = finished_tasks.filter(
            ManualAnnotationTask.file_id == task_file.file_id,
            not_(ManualAnnotationTask.is_validation),
        ).all()
        annotated_pages = set()
        for finished_annotating_task in finished_annotating_tasks:
            annotated_pages.update(finished_annotating_task.pages)
        annotated_pages = sorted(annotated_pages)
        if validation_type[0] != ValidationSchema.validation_only:
            assert task_file.annotated_pages == annotated_pages

        finished_validating_tasks = finished_tasks.filter(
            ManualAnnotationTask.file_id == task_file.file_id,
            ManualAnnotationTask.is_validation,
        ).all()
        validated_pages = set()
        for finished_validating_task in finished_validating_tasks:
            # find revisions, made by user
            revisions = get_task_revisions(
                test_session,
                tenant,
                job_id,
                finished_validating_task.id,
                task_file.file_id,
                finished_validating_task.pages,
            )
            # accumulate info about pages, validated/annotated by him
            validated, *_ = accumulate_pages_info(
                finished_validating_task.pages, revisions
            )
            validated_pages.update(validated)
        validated_pages = sorted(validated_pages)
        assert task_file.validated_pages == validated_pages
        file_pages = list(range(1, task_file.pages_number + 1))
        if task_file.status == FileStatusEnumSchema.annotated:
            assert task_file.annotated_pages == file_pages
        if task_file.status == FileStatusEnumSchema.validated:
            assert task_file.validated_pages == file_pages
            assert task_file.annotated_pages == file_pages
        if (
            task_file.annotated_pages == file_pages
            and task_file.validated_pages != file_pages
        ):
            assert task_file.status == FileStatusEnumSchema.annotated
        if (
            task_file.validated_pages == file_pages
            and task_file.annotated_pages == file_pages
        ):
            assert task_file.status == FileStatusEnumSchema.validated


@pytest.mark.integration
@pytest.mark.parametrize(
    [
        "task_id",
        "job_id",
        "dataset_status_code",
        "expected_code",
        "expected_response",
        "expected_jobs_calls",
        "expected_inner_job_status",
    ],
    [
        (
            FINISH_TASK_ID,
            FINISH_TASK_JOB_1.job_id,
            200,
            200,
            FINISH_UPDATED_TASK,
            1,
            JobStatusEnumSchema.finished,
        ),
        (
            NOT_EXISTING_ID,
            FINISH_TASK_JOB_1.job_id,
            200,
            404,
            {"detail": f"Task with id [{NOT_EXISTING_ID}] was not found."},
            0,
            JobStatusEnumSchema.in_progress,
        ),
        (
            BAD_ID,
            FINISH_TASK_JOB_1.job_id,
            200,
            422,
            {
                "detail": [
                    {
                        "loc": ["path", "task_id"],
                        "msg": "value is not a valid integer",
                        "type": "type_error.integer",
                    }
                ]
            },
            0,
            JobStatusEnumSchema.in_progress,
        ),
        (
            FINISH_TASK_ID,
            FINISH_TASK_JOB_1.job_id,
            400,
            500,
            {"detail": "Error: connection error ()"},
            1,
            JobStatusEnumSchema.in_progress,
        ),
    ],
)
@responses.activate
def test_finish_task_status_codes(
    prepare_db_for_finish_task_status_one_task,
    task_id,
    job_id,
    dataset_status_code,
    expected_code,
    expected_response,
    expected_jobs_calls,
    expected_inner_job_status,
):
    responses.add(
        responses.PUT,
        FINISH_TASK_JOB_1.callback_url,
        status=dataset_status_code,
        headers=TEST_HEADERS,
    )
    response = client.post(
        FINISH_TASK_PATH.format(task_id=task_id), headers=TEST_HEADERS
    )
    session = prepare_db_for_finish_task_status_one_task
    job = session.query(Job).get(job_id)
    assert response.status_code == expected_code
    assert job.status == expected_inner_job_status
    assert response.json() == expected_response
    assert responses.assert_call_count(
        FINISH_TASK_JOB_1.callback_url, expected_jobs_calls
    )
    check_files_finished_pages(
        prepare_db_for_finish_task_status_one_task, job_id, TEST_TENANT
    )


@pytest.mark.unittest
@pytest.mark.parametrize(
    ["db_errors"],
    [
        (DBAPIError,),
        (SQLAlchemyError,),
    ],
    indirect=["db_errors"],
)
def test_finish_task_exceptions(monkeypatch, db_errors):
    response = client.post(
        FINISH_TASK_PATH.format(task_id=FINISH_TASK_ID), headers=TEST_HEADERS
    )
    assert response.status_code == 500


@pytest.mark.integration
@pytest.mark.parametrize(
    ["exc"], [(RequestException(),), (ConnectionError(),), (Timeout(),)]
)
@responses.activate
def test_finish_task_request_exc(
    monkeypatch, prepare_db_for_finish_task_status_one_task, exc
):
    responses.add(
        responses.PUT,
        FINISH_TASK_JOB_1.callback_url,
        body=exc,
        status=500,
        headers=TEST_HEADERS,
    )
    response = client.post(
        FINISH_TASK_PATH.format(task_id=FINISH_TASK_ID), headers=TEST_HEADERS
    )
    assert response.status_code == 500


@pytest.mark.integration
@responses.activate
def test_finish_not_all_tasks_db_contain(
    prepare_db_for_finish_task_status_two_tasks_same_job,
):
    """
    In db there are two tasks with `in progress` status
    and with same job_id.
    This test puts only one task to `finished` status,
    so call to job microservice will not happen and
    no mocked response will be returned. Task will
    be successfully updated.
    """
    responses.add(
        responses.PUT,
        FINISH_TASK_JOB_1.callback_url,
        body=RequestException(),
        status=500,
        headers=TEST_HEADERS,
    )
    client.post(
        FINISH_TASK_PATH.format(task_id=FINISH_TASK_ID), headers=TEST_HEADERS
    )
    task = prepare_db_for_finish_task_status_two_tasks_same_job.query(
        ManualAnnotationTask
    ).get(FINISH_TASK_ID)
    actual_task = row_to_dict(task)
    assert actual_task == FINISH_UPDATED_TASK
    check_files_finished_pages(
        prepare_db_for_finish_task_status_two_tasks_same_job,
        FINISH_TASK_JOB_1.job_id,
        TEST_TENANT,
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ["dataset_status_code", "expected_task_in_db", "job_id"],
    [
        (200, FINISH_UPDATED_TASK, FINISH_TASK_JOB_1.job_id),
        # in this case dataset responses with 200 code,
        # so job will be finished
        (400, FINISH_TASK_1_SAME_JOB, FINISH_TASK_JOB_1.job_id),
        # in this case something wrong with dataset,
        # so task will not be updated
    ],
)
@responses.activate
def test_finish_all_tasks_db_contain(
    prepare_db_for_finish_task_with_not_in_progress_status,
    dataset_status_code,
    expected_task_in_db,
    job_id,
):
    """
    In db there are two tasks with `in progress` status,
    but with different job_id.
    """
    responses.add(
        responses.PUT,
        FINISH_TASK_JOB_1.callback_url,
        status=dataset_status_code,
        headers=TEST_HEADERS,
    )
    client.post(
        FINISH_TASK_PATH.format(task_id=FINISH_TASK_ID),
        headers=TEST_HEADERS,
    )
    task = prepare_db_for_finish_task_with_not_in_progress_status.query(
        ManualAnnotationTask
    ).get(FINISH_TASK_ID)
    actual_task = row_to_dict(task)
    assert actual_task == expected_task_in_db
    check_files_finished_pages(
        prepare_db_for_finish_task_with_not_in_progress_status,
        job_id,
        TEST_TENANT,
    )


@pytest.mark.integration
def test_finish_task_not_in_progress_status(
    prepare_db_for_finish_task_with_not_in_progress_status,
):
    response = client.post(
        FINISH_TASK_PATH.format(task_id=TASK_NOT_IN_PROGRESS_STATUS["id"]),
        headers=TEST_HEADERS,
    )
    assert response.status_code == 400


ANNOTATION_TASKS_TO_FINISH = [
    {
        "id": 9,
        "file_id": FINISH_TASK_FILE_3.file_id,
        "pages": [6, 7],
        "job_id": FINISH_TASK_JOB_3.job_id,
        "user_id": FINISH_TASK_USER_1.user_id,
        "is_validation": False,
        "status": TaskStatusEnumSchema.in_progress,
        "deadline": None,
    },
    {
        "id": 10,
        "file_id": FINISH_TASK_FILE_3.file_id,
        "pages": [8, 9],
        "job_id": FINISH_TASK_JOB_3.job_id,
        "user_id": FINISH_TASK_USER_1.user_id,
        "is_validation": False,
        "status": TaskStatusEnumSchema.in_progress,
        "deadline": None,
    },
]


VALIDATION_TASKS_TO_FINISH = [
    {
        "id": 20,
        "file_id": FINISH_TASK_FILE_3.file_id,
        "pages": [1, 2, 3, 4, 5, 6, 7, 8, 9],
        "job_id": FINISH_TASK_JOB_3.job_id,
        "user_id": FINISH_TASK_USER_1.user_id,
        "is_validation": True,
        "status": TaskStatusEnumSchema.in_progress,
        "deadline": None,
    },
    {
        "id": 21,
        "file_id": FINISH_TASK_FILE_3.file_id,
        "pages": [1, 2, 3, 4, 5, 6, 7, 8, 9],
        "job_id": FINISH_TASK_JOB_3.job_id,
        "user_id": FINISH_TASK_USER_1.user_id,
        "is_validation": True,
        "status": TaskStatusEnumSchema.in_progress,
        "deadline": None,
    },
]


VALIDATION_TASKS_TO_READY = [
    {
        "id": 11,
        "file_id": FINISH_TASK_FILE_3.file_id,
        "pages": [1, 2, 3, 4, 5],
        "job_id": FINISH_TASK_JOB_3.job_id,
        "user_id": FINISH_TASK_USER_1.user_id,
        "is_validation": True,
        "status": TaskStatusEnumSchema.pending,
        "deadline": None,
    },
    {
        "id": 12,
        "file_id": FINISH_TASK_FILE_3.file_id,
        "pages": [1, 2, 3, 6],
        "job_id": FINISH_TASK_JOB_3.job_id,
        "user_id": FINISH_TASK_USER_1.user_id,
        "is_validation": True,
        "status": TaskStatusEnumSchema.pending,
        "deadline": None,
    },
    {
        "id": 13,
        "file_id": FINISH_TASK_FILE_3.file_id,
        "pages": [4, 7],
        "job_id": FINISH_TASK_JOB_3.job_id,
        "user_id": FINISH_TASK_USER_1.user_id,
        "is_validation": True,
        "status": TaskStatusEnumSchema.pending,
        "deadline": None,
    },
    {
        "id": 14,
        "file_id": FINISH_TASK_FILE_3.file_id,
        "pages": [8, 9],
        "job_id": FINISH_TASK_JOB_3.job_id,
        "user_id": FINISH_TASK_USER_1.user_id,
        "is_validation": True,
        "status": TaskStatusEnumSchema.pending,
        "deadline": None,
    },
    {
        "id": 15,
        "file_id": FINISH_TASK_FILE_3.file_id,
        "pages": [1, 2, 3, 4, 5],
        "job_id": FINISH_TASK_JOB_3.job_id,
        "user_id": FINISH_TASK_USER_1.user_id,
        "is_validation": True,
        "status": TaskStatusEnumSchema.ready,
        "deadline": None,
    },
    {
        "id": 18,
        "file_id": FINISH_TASK_FILE_3.file_id,
        "pages": [1, 2, 3, 4, 5],
        "job_id": FINISH_TASK_JOB_3.job_id,
        "user_id": FINISH_TASK_USER_1.user_id,
        "is_validation": True,
        "status": TaskStatusEnumSchema.finished,
        "deadline": None,
    },
    {
        "id": 19,
        "file_id": FINISH_TASK_FILE_1.file_id,
        "pages": [1, 2, 3, 4, 5],
        "job_id": FINISH_TASK_JOB_1.job_id,
        "user_id": FINISH_TASK_USER_1.user_id,
        "is_validation": True,
        "status": TaskStatusEnumSchema.pending,
        "deadline": None,
    },
    {
        "id": 33,
        "file_id": FINISH_TASK_FILE_3.file_id,
        "pages": [1, 2, 3, 4, 5],
        "job_id": FINISH_TASK_JOB_3.job_id,
        "user_id": FINISH_TASK_USER_1.user_id,
        "is_validation": False,
        "status": TaskStatusEnumSchema.finished,
        "deadline": None,
    },
]


@pytest.mark.integration
@pytest.mark.parametrize(
    [
        "annotation_finish_task",
        "validation_tasks_changing_status",
        "validation_tasks_remaining_status",
    ],
    [
        (
            ANNOTATION_TASKS_TO_FINISH[0],
            VALIDATION_TASKS_TO_READY[:2],
            [VALIDATION_TASKS_TO_READY[3]],
        ),
        (
            ANNOTATION_TASKS_TO_FINISH[1],
            [VALIDATION_TASKS_TO_READY[0], VALIDATION_TASKS_TO_READY[3]],
            VALIDATION_TASKS_TO_READY[1:3],
        ),
    ],
)
@responses.activate
def test_finish_tasks_validation_tasks_unblocking(
    prepare_db_for_finish_task_change_validation_status,
    annotation_finish_task,
    validation_tasks_changing_status,
    validation_tasks_remaining_status,
):
    """Checks that statuses for validation tasks changes for tasks where
    'pages' is subset for annotated file's pages only. Considers annotated
    earlier pages as well as pages annotated in finishing task.
    """
    responses.add(
        responses.PUT,
        FINISH_TASK_JOB_1.callback_url,
        status=200,
        headers=TEST_HEADERS,
    )
    session = prepare_db_for_finish_task_change_validation_status
    validation_tasks_changing_ids = [
        task["id"] for task in validation_tasks_changing_status
    ]
    validation_tasks_remaining_ids = [
        task["id"] for task in validation_tasks_remaining_status
    ]
    tasks_with_changing_status = session.query(ManualAnnotationTask).filter(
        ManualAnnotationTask.id.in_(validation_tasks_changing_ids)
    )
    tasks_with_remaining_status = session.query(ManualAnnotationTask).filter(
        ManualAnnotationTask.id.in_(validation_tasks_remaining_ids)
    )
    annotation_task = ManualAnnotationTask(**annotation_finish_task)
    session.add(annotation_task)
    session.commit()
    client.post(
        FINISH_TASK_PATH.format(task_id=annotation_task.id),
        headers=TEST_HEADERS,
    )
    for task in tasks_with_changing_status:
        assert task.status == TaskStatusEnumSchema.ready
    for task in tasks_with_remaining_status:
        assert task.status == TaskStatusEnumSchema.pending


@pytest.mark.integration
@responses.activate
def test_finish_task_pending_validation_unblocking(
    prepare_db_for_finish_task_change_validation_status,
):
    """Checks that status for task changes to 'ready' only when it is
    validation task with 'pending' status within same job_id.
    """
    responses.add(
        responses.PUT,
        FINISH_TASK_JOB_1.callback_url,
        status=200,
        headers=TEST_HEADERS,
    )
    session = prepare_db_for_finish_task_change_validation_status
    annotation_finish_task = ManualAnnotationTask(
        **ANNOTATION_TASKS_TO_FINISH[0]
    )
    session.add(annotation_finish_task)
    session.commit()
    client.post(
        FINISH_TASK_PATH.format(task_id=annotation_finish_task.id),
        headers=TEST_HEADERS,
    )
    test_tasks = [
        ANNOTATION_TASKS_TO_FINISH[0],
        *VALIDATION_TASKS_TO_READY[4:],
    ]
    not_changing_tasks_ids = (task["id"] for task in test_tasks)
    validation_not_changing_tasks = (
        session.query(ManualAnnotationTask)
        .filter(ManualAnnotationTask.id.in_(not_changing_tasks_ids))
        .order_by(asc(ManualAnnotationTask.id))
        .all()
    )
    for task_db, test_task in zip(validation_not_changing_tasks, test_tasks):
        assert task_db.status == test_task["status"]


@pytest.mark.integration
@responses.activate
def test_finish_tasks_failed_validation_statuses(
    monkeypatch, prepare_db_for_finish_task_failed_validation_status
):
    """Checks that new annotation tasks for validation-failed pages are created
    in 'ready' status, and new validation tasks - in 'pending' status.
    """
    session = prepare_db_for_finish_task_failed_validation_status
    failed = {1, 2, 3}
    end_task_schema = {
        "annotation_user_for_failed_pages": "auto",
    }
    accumulate_pages = set(), failed, set(), set(), None
    monkeypatch.setattr(
        "annotation.annotations.main.accumulate_pages_info",
        Mock(return_value=accumulate_pages),
    )
    responses.add(
        responses.PUT,
        FINISH_TASK_JOB_1.callback_url,
        status=200,
        headers=TEST_HEADERS,
    )
    validation_finish_task = ManualAnnotationTask(
        **VALIDATION_TASKS_TO_FINISH[0]
    )
    session.add(validation_finish_task)
    session.commit()
    client.post(
        FINISH_TASK_PATH.format(task_id=validation_finish_task.id),
        headers=TEST_HEADERS,
        json=end_task_schema,
    )
    new_tasks = (
        session.query(ManualAnnotationTask)
        .filter(ManualAnnotationTask.id != validation_finish_task.id)
        .all()
    )
    for task in new_tasks:
        assert (
            task.status == TaskStatusEnumSchema.pending
            if task.is_validation
            else task.status == TaskStatusEnumSchema.ready
        )


@pytest.mark.integration
@responses.activate
def test_finish_tasks_reannotation_statuses(
    monkeypatch, prepare_db_for_finish_task_failed_validation_status
):
    """Checks that new validation tasks for reannotated by validator pages are
    created in 'ready' status.
    """
    session = prepare_db_for_finish_task_failed_validation_status
    annotated = {4}
    end_task_schema = {
        "validation_user_for_reannotated_pages": "auto",
    }
    accumulate_pages = set(), set(), annotated, set(), None
    monkeypatch.setattr(
        "annotation.annotations.main.accumulate_pages_info",
        Mock(return_value=accumulate_pages),
    )
    responses.add(
        responses.PUT,
        FINISH_TASK_JOB_1.callback_url,
        status=200,
        headers=TEST_HEADERS,
    )
    validation_finish_task = ManualAnnotationTask(
        **VALIDATION_TASKS_TO_FINISH[1]
    )
    session.add(validation_finish_task)
    session.commit()
    client.post(
        FINISH_TASK_PATH.format(task_id=validation_finish_task.id),
        headers=TEST_HEADERS,
        json=end_task_schema,
    )
    new_tasks = (
        session.query(ManualAnnotationTask)
        .filter(ManualAnnotationTask.id != validation_finish_task.id)
        .all()
    )
    for task in new_tasks:
        assert task.status == TaskStatusEnumSchema.ready


def test_finish_task_initial_annotator_deleted(
    prepare_db_for_finish_task_check_deleted_annotators,
):
    session = prepare_db_for_finish_task_check_deleted_annotators
    session.query(ManualAnnotationTask).filter(
        ManualAnnotationTask.id
        == FINISH_TASK_CHECK_DELETE_USER_ANNOTATOR_2["id"]
    ).delete()
    session.commit()
    session.query(User).filter(
        User.user_id == FINISH_TASK_USER_2.user_id
    ).delete()
    session.commit()

    end_task_schema = {
        "annotation_user_for_failed_pages": "initial",
    }
    response = client.post(
        FINISH_TASK_PATH.format(
            task_id=FINISH_TASK_CHECK_DELETE_USER_VALIDATOR["id"]
        ),
        headers=TEST_HEADERS,
        json=end_task_schema,
    )
    assert response.status_code == 400
    assert response.json() == {
        "detail": "It`s not possible to create an annotation task "
        "for the initial user(s).They were deleted."
    }


def test_finish_task_should_work_with_pages_covered_extensively_once(
    prepare_db_with_extensive_coverage_annotations,
):
    # given
    (
        db,
        annotation_tasks,
        validation,
    ) = prepare_db_with_extensive_coverage_annotations
    for obj in [*annotation_tasks, validation]:
        db.merge(ManualAnnotationTask(**obj))
    db.commit()

    # when
    response = client.post(
        FINISH_TASK_PATH.format(task_id=annotation_tasks[0]["id"]),
        headers=TEST_HEADERS,
    )

    # then
    assert response
    task_file = (
        db.query(File)
        .filter(
            File.job_id == annotation_tasks[0]["job_id"],
            File.file_id == annotation_tasks[0]["file_id"],
        )
        .first()
    )
    assert not task_file.annotated_pages


def test_finish_task_should_work_with_some_pages_covered_extensively_twice(
    prepare_db_with_extensive_coverage_annotations,
):
    # given
    (
        db,
        annotation_tasks,
        validation,
    ) = prepare_db_with_extensive_coverage_annotations
    annotation_tasks[0]["status"] = TaskStatusEnumSchema.finished
    for obj in [*annotation_tasks, validation]:
        db.merge(ManualAnnotationTask(**obj))
    db.commit()

    # when
    response = client.post(
        FINISH_TASK_PATH.format(task_id=annotation_tasks[1]["id"]),
        headers=TEST_HEADERS,
    )

    # then
    assert response
    task_file = (
        db.query(File)
        .filter(
            File.job_id == annotation_tasks[0]["job_id"],
            File.file_id == annotation_tasks[0]["file_id"],
        )
        .first()
    )
    assert task_file.annotated_pages == sorted(
        set(annotation_tasks[0]["pages"]).intersection(
            set(annotation_tasks[1]["pages"])
        )
    )


def test_finish_task_should_work_with_all_pages_covered_extensively_twice(
    prepare_db_with_extensive_coverage_annotations,
    mock_minio_empty_bucket,
):
    # given
    (
        db,
        annotation_tasks,
        validation,
    ) = prepare_db_with_extensive_coverage_annotations
    annotation_tasks[0]["status"] = TaskStatusEnumSchema.finished
    annotation_tasks[1]["status"] = TaskStatusEnumSchema.finished
    for obj in [*annotation_tasks, validation]:
        db.merge(ManualAnnotationTask(**obj))
    db.commit()

    # when
    with patch(
        "annotation.tasks.services.get_file_path_and_bucket",
        return_value=("", ""),
    ):
        response = client.post(
            FINISH_TASK_PATH.format(task_id=annotation_tasks[2]["id"]),
            headers=TEST_HEADERS,
        )

    # then
    assert response
    task_file = (
        db.query(File)
        .filter(
            File.job_id == annotation_tasks[0]["job_id"],
            File.file_id == annotation_tasks[0]["file_id"],
        )
        .first()
    )
    all_anno_pages = (
        annotation_tasks[0]["pages"]
        + annotation_tasks[1]["pages"]
        + annotation_tasks[2]["pages"]
    )
    assert task_file.annotated_pages == sorted(set(all_anno_pages))
    assert task_file.annotated_pages == task_file.distributed_annotating_pages
    validation_task = (
        db.query(ManualAnnotationTask)
        .filter(
            ManualAnnotationTask.job_id == annotation_tasks[0]["job_id"],
            ManualAnnotationTask.is_validation.is_(True),
            ManualAnnotationTask.file_id == annotation_tasks[0]["file_id"],
        )
        .first()
    )
    assert validation_task.status == TaskStatusEnumSchema.ready


@patch("annotation.tasks.services.AGREEMENT_SCORE_MIN_MATCH", 0.7)
@patch("annotation.tasks.resources.AGREEMENT_SCORE_ENABLED", "true")
def test_finish_task_with_agreement_score_enabled_score_matched(
    prepare_db_with_extensive_coverage_annotations,
    mock_minio_empty_bucket,
):
    (
        db,
        annotation_tasks,
        validation,
    ) = prepare_db_with_extensive_coverage_annotations
    annotation_tasks[0]["status"] = TaskStatusEnumSchema.finished
    annotation_tasks[1]["status"] = TaskStatusEnumSchema.finished
    for obj in [*annotation_tasks, validation]:
        db.merge(ManualAnnotationTask(**obj))
    db.commit()

    with patch(
        "annotation.tasks.services.get_agreement_score",
        return_value=AGREEMENT_SCORE_RESPONSE,
    ) as mock1:
        with patch(
            "annotation.tasks.services.get_file_path_and_bucket",
            return_value=("", ""),
        ) as mock2:
            with patch(
                "annotation.tasks.resources.update_job_status"
            ) as mock4:
                response = client.post(
                    FINISH_TASK_PATH.format(task_id=annotation_tasks[2]["id"]),
                    headers=TEST_HEADERS,
                )
    assert response

    mock1.assert_called_once()
    mock2.assert_called()
    mock4.assert_called_once()
    validation_task = (
        db.query(ManualAnnotationTask)
        .filter(
            ManualAnnotationTask.job_id == annotation_tasks[0]["job_id"],
            ManualAnnotationTask.is_validation.is_(True),
            ManualAnnotationTask.file_id == annotation_tasks[0]["file_id"],
        )
        .first()
    )
    assert validation_task.status == TaskStatusEnumSchema.finished

    job = db.query(Job).filter(Job.job_id == validation_task.job_id).first()
    assert job.status == JobStatusEnumSchema.finished
    assert db.query(AgreementMetrics).count() == 6


@patch("annotation.tasks.services.AGREEMENT_SCORE_MIN_MATCH", 0.99)
@patch("annotation.tasks.resources.AGREEMENT_SCORE_ENABLED", "true")
def test_finish_task_with_agreement_score_enabled_score_not_matched(
    prepare_db_with_extensive_coverage_annotations,
    mock_minio_empty_bucket,
):
    (
        db,
        annotation_tasks,
        validation,
    ) = prepare_db_with_extensive_coverage_annotations
    annotation_tasks[0]["status"] = TaskStatusEnumSchema.finished
    annotation_tasks[1]["status"] = TaskStatusEnumSchema.finished
    for obj in [*annotation_tasks, validation]:
        db.merge(ManualAnnotationTask(**obj))
    db.commit()

    with patch(
        "annotation.tasks.services.get_agreement_score",
        return_value=AGREEMENT_SCORE_RESPONSE,
    ) as mock1:
        with patch(
            "annotation.tasks.services.get_file_path_and_bucket",
            return_value=("", ""),
        ) as mock2:
            with patch(
                "annotation.tasks.resources.update_job_status"
            ) as mock4:
                response = client.post(
                    FINISH_TASK_PATH.format(task_id=annotation_tasks[2]["id"]),
                    headers=TEST_HEADERS,
                )
    assert response

    mock1.assert_called_once()
    mock2.assert_called()
    mock4.assert_not_called()
    validation_task = (
        db.query(ManualAnnotationTask)
        .filter(
            ManualAnnotationTask.job_id == annotation_tasks[0]["job_id"],
            ManualAnnotationTask.is_validation.is_(True),
            ManualAnnotationTask.file_id == annotation_tasks[0]["file_id"],
        )
        .first()
    )
    assert validation_task.status == TaskStatusEnumSchema.ready

    job = db.query(Job).filter(Job.job_id == validation_task.job_id).first()
    assert job.status == JobStatusEnumSchema.in_progress


@patch("annotation.tasks.services.AGREEMENT_SCORE_MIN_MATCH", 0.5)
@patch.dict(os.environ, {"AGREEMENT_SCORE_ENABLED": "true"})
def test_finish_task_with_agreement_score_enabled_annotation_not_finished(
    prepare_db_with_extensive_coverage_annotations_same_pages,
    mock_minio_empty_bucket,
):
    (
        db,
        annotation_tasks,
        validation,
    ) = prepare_db_with_extensive_coverage_annotations_same_pages
    annotation_tasks[0]["status"] = TaskStatusEnumSchema.finished
    annotation_tasks[1]["status"] = TaskStatusEnumSchema.ready
    for obj in [*annotation_tasks, validation]:
        db.merge(ManualAnnotationTask(**obj))
    db.commit()

    with patch(
        "annotation.tasks.services.get_agreement_score",
        return_value=AGREEMENT_SCORE_RESPONSE,
    ) as mock1:
        with patch(
            "annotation.tasks.services.get_file_path_and_bucket",
            return_value=("", ""),
        ) as mock2:
            with patch(
                "annotation.tasks.resources.update_job_status"
            ) as mock4:
                response = client.post(
                    FINISH_TASK_PATH.format(task_id=annotation_tasks[2]["id"]),
                    headers=TEST_HEADERS,
                )
    assert response

    mock1.assert_not_called()
    mock2.assert_called_once()
    mock4.assert_not_called()
    validation_task = (
        db.query(ManualAnnotationTask)
        .filter(
            ManualAnnotationTask.job_id == annotation_tasks[0]["job_id"],
            ManualAnnotationTask.is_validation.is_(True),
            ManualAnnotationTask.file_id == annotation_tasks[0]["file_id"],
        )
        .first()
    )
    assert validation_task.status == TaskStatusEnumSchema.ready

    job = db.query(Job).filter(Job.job_id == validation_task.job_id).first()
    assert job.status == JobStatusEnumSchema.in_progress


TRANSFER_ANNOTATIONS_USERS = [
    "01ec1df0-516d-4905-a902-fbd1ed99a49d",
    "02ec1df0-526d-4905-a902-fbd1ed99a49d",
    "03ec1df0-536d-4905-a902-fbd1ed99a49d",
]
TRANSFER_ANNOTATIONS_CATEGORIES = [
    Category(id="Test111", name="Test1", type=CategoryTypeSchema.box),
    Category(id="Test222", name="Test2", type=CategoryTypeSchema.box),
]
TRANSFER_ANNOTATIONS_FILE = File(
    file_id=54321,
    tenant=TEST_TENANT,
    job_id=123456,
    pages_number=1,
    distributed_annotating_pages=[1],
    distributed_validating_pages=[1],
    status=FileStatusEnumSchema.pending,
)
TRANSFER_ANNOTATIONS_JOB = Job(
    job_id=TRANSFER_ANNOTATIONS_FILE.job_id,
    callback_url="http://www.test.com/test1",
    annotators=[
        User(user_id=TRANSFER_ANNOTATIONS_USERS[0]),
        User(user_id=TRANSFER_ANNOTATIONS_USERS[1]),
    ],
    validators=[User(user_id=TRANSFER_ANNOTATIONS_USERS[2])],
    validation_type=ValidationSchema.extensive_coverage,
    extensive_coverage=2,
    files=[TRANSFER_ANNOTATIONS_FILE],
    is_auto_distribution=True,
    categories=TRANSFER_ANNOTATIONS_CATEGORIES,
    deadline=None,
    tenant=TEST_TENANT,
    status=JobStatusEnumSchema.in_progress,
)
TRANSFER_ANNOTATIONS_TASKS = [
    {
        "id": 1,
        "file_id": TRANSFER_ANNOTATIONS_FILE.file_id,
        "pages": [1],
        "job_id": TRANSFER_ANNOTATIONS_FILE.job_id,
        "user_id": TRANSFER_ANNOTATIONS_USERS[0],
        "is_validation": False,
        "status": TaskStatusEnumSchema.finished,
        "deadline": None,
    },
    {
        "id": 2,
        "file_id": TRANSFER_ANNOTATIONS_FILE.file_id,
        "pages": [1],
        "job_id": TRANSFER_ANNOTATIONS_FILE.job_id,
        "user_id": TRANSFER_ANNOTATIONS_USERS[1],
        "is_validation": False,
        "status": TaskStatusEnumSchema.in_progress,
        "deadline": None,
    },
    {
        "id": 3,
        "file_id": TRANSFER_ANNOTATIONS_FILE.file_id,
        "pages": [1],
        "job_id": TRANSFER_ANNOTATIONS_FILE.job_id,
        "user_id": TRANSFER_ANNOTATIONS_USERS[2],
        "is_validation": True,
        "status": TaskStatusEnumSchema.pending,
        "deadline": None,
    },
]
TRANSFER_ANNOTATIONS_DOCS = [
    AnnotatedDoc(
        revision="1",
        user=TRANSFER_ANNOTATIONS_TASKS[0]["user_id"],
        pipeline=None,
        file_id=TRANSFER_ANNOTATIONS_TASKS[0]["file_id"],
        job_id=TRANSFER_ANNOTATIONS_TASKS[0]["job_id"],
        pages={"1": "11"},
        validated=[],
        failed_validation_pages=[],
        tenant=TEST_TENANT,
        task_id=TRANSFER_ANNOTATIONS_TASKS[0]["id"],
        date="2023-1-01T00:00:00",
        categories=[
            category.name for category in TRANSFER_ANNOTATIONS_CATEGORIES
        ],
    ),
    AnnotatedDoc(
        revision="2",
        user=TRANSFER_ANNOTATIONS_TASKS[1]["user_id"],
        pipeline=None,
        file_id=TRANSFER_ANNOTATIONS_TASKS[1]["file_id"],
        job_id=TRANSFER_ANNOTATIONS_TASKS[1]["job_id"],
        pages={"1": "22"},
        validated=[],
        failed_validation_pages=[],
        tenant=TEST_TENANT,
        task_id=TRANSFER_ANNOTATIONS_TASKS[1]["id"],
        date="2023-1-01T00:00:00",
        categories=[
            category.name for category in TRANSFER_ANNOTATIONS_CATEGORIES
        ],
    ),
]
TOKEN_1 = {"id": 111, "other": 1}
TOKEN_2 = {"id": 222, "other": 2}
OBJ_1 = {"type": "text", "data": {"tokens": [TOKEN_1, TOKEN_2]}, "other": 2}
EXPECTED_OBJ_1 = {
    "type": "text",
    "data": {
        "tokens": [{"id": TOKEN_1["id"]}, {"id": TOKEN_2["id"]}],
        "dataAttributes": [],
    },
    "other": 2,
}
OBJ_2 = {"same": 3}
TRANSFER_ANNOTATIONS_PAGES = {
    "11": {
        "page_num": 1,
        "size": {"width": 1.0, "height": 1.0},
        "objs": [
            {"id": 1, **OBJ_1},
            {"id": 2, **OBJ_2},
            {"id": 3, "key": [1, 2, 3]},
        ],
    },
    "22": {
        "page_num": 1,
        "size": {"width": 1.0, "height": 1.0},
        "objs": [{"id": 4, **OBJ_1}, {"id": 5, **OBJ_2}],
    },
}


def test_transfer_annotations(
    prepare_db_transfer_annotations,
    prepare_minio_transfer_annotations,
):
    db = prepare_db_transfer_annotations
    with patch(
        "annotation.tasks.services.get_file_path_and_bucket",
        return_value=("", ""),
    ):
        finish_response = client.post(
            FINISH_TASK_PATH.format(
                task_id=TRANSFER_ANNOTATIONS_TASKS[1]["id"]
            ),
            headers=TEST_HEADERS,
        )

    assert finish_response.status_code == 200

    annotation_task = (
        db.query(ManualAnnotationTask)
        .filter(
            ManualAnnotationTask.id == TRANSFER_ANNOTATIONS_TASKS[1]["id"],
        )
        .first()
    )
    validation_task = (
        db.query(ManualAnnotationTask)
        .filter(
            ManualAnnotationTask.id == TRANSFER_ANNOTATIONS_TASKS[2]["id"],
        )
        .first()
    )

    assert annotation_task.status == TaskStatusEnumSchema.finished
    assert validation_task.status == TaskStatusEnumSchema.in_progress

    new_revision_number = (
        db.query(AnnotatedDoc)
        .filter(
            AnnotatedDoc.file_id == TRANSFER_ANNOTATIONS_FILE.file_id,
            AnnotatedDoc.job_id == TRANSFER_ANNOTATIONS_JOB.job_id,
            AnnotatedDoc.user == TRANSFER_ANNOTATIONS_TASKS[-1]["user_id"],
        )
        .first()
        .revision
    )

    all_revisions = client.get(
        f"/annotation/{TRANSFER_ANNOTATIONS_JOB.job_id}/"
        f"{TRANSFER_ANNOTATIONS_FILE.file_id}/latest_by_user",
        headers=TEST_HEADERS,
        params={"page_numbers": [1]},
    )
    new_revision = next(
        (
            revision
            for revision in all_revisions.json()["1"]
            if revision["revision"] == new_revision_number
        ),
        None,
    )
    assert new_revision

    new_revision_objs = [
        {key: obj[key] for key in obj if key != "id"}
        for obj in new_revision["objs"]
    ]
    assert new_revision_objs == [EXPECTED_OBJ_1, OBJ_2]
