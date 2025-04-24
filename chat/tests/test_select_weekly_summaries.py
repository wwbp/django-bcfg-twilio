from unittest.mock import MagicMock, patch
from django.urls import reverse
import pytest

from chat.models import Summary


@pytest.fixture
def mock_http_client_instance():
    with patch("chat.services.send.httpx.Client") as http_client_mock:
        mock_client_instance = MagicMock()
        mock_client_instance.post = MagicMock()
        mock_client_instance.post.return_value.status_code = 200
        http_client_mock.return_value.__enter__.return_value = mock_client_instance
        yield mock_client_instance


def test_select_weekly_summaries(mock_http_client_instance, summary_factory, admin_client, celery_task_always_eager):
    school1_week1_summaries = summary_factory.create_batch(10, week_number=1, school_name="School 1")
    school1_week2_summaries = summary_factory.create_batch(10, week_number=2, school_name="School 1")
    school2_week1_summaries = summary_factory.create_batch(10, week_number=1, school_name="School 2")

    # Select summaries for week 1 of School 1
    url = reverse("admin:chat_summary_changelist")
    summary_ids_to_select = [
        school1_week1_summaries[0].id,
        school1_week1_summaries[1].id,
        school1_week1_summaries[2].id,
        school2_week1_summaries[0].id,
        school1_week2_summaries[0].id,
    ]
    data = {
        "action": "select_summaries",
        "_selected_action": summary_ids_to_select,
    }
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    seleced_summaries = Summary.objects.filter(selected=True).all()
    assert len(seleced_summaries) == len(summary_ids_to_select)
    assert set(summary_ids_to_select) == {s.id for s in seleced_summaries}
    assert mock_http_client_instance.post.call_count == 3


def test_select_then_deselect_weekly_summaries(
    mock_http_client_instance, summary_factory, admin_client, celery_task_always_eager
):
    school1_week1_summaries = summary_factory.create_batch(10, week_number=1, school_name="School 1")

    # First select 3 summaries
    admin_url = reverse("admin:chat_summary_changelist")
    summary_ids_to_select = [
        school1_week1_summaries[0].id,
        school1_week1_summaries[1].id,
        school1_week1_summaries[2].id,
    ]
    data = {
        "action": "select_summaries",
        "_selected_action": summary_ids_to_select,
    }
    response = admin_client.post(admin_url, data, follow=True)
    assert response.status_code == 200
    seleced_summaries = Summary.objects.filter(selected=True).all()
    assert len(seleced_summaries) == len(summary_ids_to_select)
    assert set(summary_ids_to_select) == {s.id for s in seleced_summaries}
    assert mock_http_client_instance.post.call_count == 1
    post_url = mock_http_client_instance.post.call_args_list[0][0][0]
    assert post_url.endswith("/ai/api/summary/school/School 1/week/1")  # note httpx will urlencode
    payload = mock_http_client_instance.post.call_args_list[0][1]["json"]
    assert payload == {
        "summaries": [
            school1_week1_summaries[0].summary,
            school1_week1_summaries[1].summary,
            school1_week1_summaries[2].summary,
        ]
    }

    # Now deslect 2 summaries
    summary_ids_to_deselect = [
        school1_week1_summaries[0].id,
        school1_week1_summaries[1].id,
    ]
    data = {
        "action": "deselect_summaries",
        "_selected_action": summary_ids_to_deselect,
    }
    response = admin_client.post(admin_url, data, follow=True)
    assert response.status_code == 200
    selected_summaries = Summary.objects.filter(selected=True).all()
    assert len(selected_summaries) == 1
    assert selected_summaries[0].id == school1_week1_summaries[2].id
    assert mock_http_client_instance.post.call_count == 2
    post_url = mock_http_client_instance.post.call_args_list[1][0][0]
    assert post_url.endswith("/ai/api/summary/school/School 1/week/1")  # note httpx will urlencode
    payload = mock_http_client_instance.post.call_args_list[1][1]["json"]
    assert payload == {
        "summaries": [
            school1_week1_summaries[2].summary,
        ]
    }


def test_select_weekly_summaries_exceed_limit_for_school(
    mock_http_client_instance, summary_factory, admin_client, celery_task_always_eager
):
    school1_week1_summaries = summary_factory.create_batch(10, week_number=1, school_name="School 1")
    school2_week1_summaries = summary_factory.create_batch(10, week_number=1, school_name="School 2")

    # Select summaries for week 1 of School 1
    url = reverse("admin:chat_summary_changelist")
    summary_ids_to_select = [
        school1_week1_summaries[0].id,
        school1_week1_summaries[1].id,
        school1_week1_summaries[2].id,
        school2_week1_summaries[0].id,
        school2_week1_summaries[1].id,
        school2_week1_summaries[2].id,
        school2_week1_summaries[3].id,
    ]
    data = {
        "action": "select_summaries",
        "_selected_action": summary_ids_to_select,
    }
    response = admin_client.post(url, data, follow=True)
    assert response.status_code == 200
    assert (
        "Selecting these options would result in the following schools having more than 3 for a given week: "
        in response.text
    )
    seleced_summaries = Summary.objects.filter(selected=True).all()
    assert len(seleced_summaries) == 0
    assert mock_http_client_instance.post.call_count == 0
