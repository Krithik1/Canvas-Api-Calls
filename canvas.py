import datetime
import json
import os

import dotenv
import pandas as pd
import requests


class Canvas:
    def __init__(self) -> None:
        # load variables from .env file
        dotenv.load_dotenv(dotenv.find_dotenv())

        # Static settings
        # Using a base urls is useful for switching between test and production environments easily
        self.BASE_URL = os.environ.get("CANVAS_URL", "https://canvas.ubc.ca")
        self.PER_PAGE = int(os.environ.get("CANVAS_PER_PAGE", "100"))

        # ensure access token is available
        self.TOKEN = os.environ.get("CANVAS_ACCESS_TOKEN")
        if self.TOKEN == None:
            print("No access token found. Please set `CANVAS_ACCESS_TOKEN`")
            exit()
        self.auth_header = {
            "Authorization": "Bearer " + self.TOKEN
        }  # setup the authorization header to be used later

        # ensure that COURSE_STATE is valid
        self.COURSE_STATE = os.environ.get("CANVAS_COURSE_STATE")
        if not self.COURSE_STATE in [
            "unpublished",
            "available",
            "completed",
            "deleted",
        ]:
            print(
                "Invalid course state. Please set `CANVAS_COURSE_STATE` to one of [unpublished, available, completed, deleted]"
            )
            exit()

    def general_get(self, request_url: str, params: dict) -> pd.DataFrame:
        all_data = []
        while True:
            r = requests.get(request_url, headers=self.auth_header, params=params)
            # always take care to handle request errors
            r.raise_for_status()  # raise error if 4xx or 5xx
            data = r.json()
            if len(data) == 0:
                break
            all_data += data
            print("Finished processing page: " + str(params["page"]))
            params["page"] += 1

        if len(all_data) == 0:
            return None

        return pd.DataFrame(all_data)

    def handle_courses_df(self, courses_df: pd.DataFrame) -> str:
        if courses_df is None:
            return "No courses found to report on."
        courses_df = courses_df[courses_df.name.notnull()]
        result = courses_df.to_string(
            columns=[
                "id",
                "name",
                "course_code",
                "workflow_state",
                "start_at",
                "end_at",
                "total_students",
            ]
        )
        return result

    def get_courses(self) -> str:
        request_url = self.BASE_URL + "/api/v1/courses"
        params = {
            "per_page": str(self.PER_PAGE),
            "page": 1,
            "state[]": [self.COURSE_STATE],
            "include[]": ["total_students"],
        }
        return self.handle_courses_df(self.general_get(request_url, params))

    def handle_assignment_df(self, assignments_df: pd.DataFrame) -> list:
        if assignments_df is None:
            return []
        dt = datetime.date.today()
        dt = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        current_time = datetime.datetime.strptime(dt, "%Y-%m-%dT%H:%M:%SZ")

        upcoming_assignments = []

        for date in assignments_df["due_at"]:
            if date == None:
                continue
            date = datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
            if date >= current_time:
                date_str = date.strftime("%B %d, %Y")
                time_str = date.strftime("%I:%M %p")
                friendly_str = f"{date_str} at {time_str}"
                upcoming_assignments.append(friendly_str)
        return upcoming_assignments

    def get_assignments(self, course_id: int) -> list:
        request_url = self.BASE_URL + f"/api/v1/courses/{course_id}/assignments"
        params = {
            "include[]": ["all_dates"],
            "order_by": "name",
            "per_page": self.PER_PAGE,
            "page": 1,
            "state": self.COURSE_STATE,
        }
        return self.handle_assignment_df(self.general_get(request_url, params))
