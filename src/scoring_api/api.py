#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import datetime
import logging
import hashlib
import uuid
from abc import abstractmethod, ABC
from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Sized, Iterable

from scoring_api.store import RedisStore, Storage
from src.scoring_api.scoring import get_score, get_interests

SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}


class ValidationError(Exception):
    pass


class Field:
    def __init__(self, required: bool = False, nullable: bool = False):
        self.required = required
        self.nullable = nullable

    def validate(self, value: Any) -> bool:
        if self.required and value is None:
            raise ValidationError("Поле обязательное")
        if not self.nullable and value is None:
            raise ValidationError("Поле обязательное")
        return True


class CharField(Field):

    def validate(self, value: str | None) -> bool:
        if super().validate(value):
            if not value:
                return True

            if isinstance(value, str):
                return True
        raise ValidationError("Поле не является строкой")


class ArgumentsField(Field):

    def validate(self, value: dict[str, Any]) -> bool:
        if super().validate(value):
            if isinstance(value, dict):
                return True
        raise ValidationError("Переданные аргументы имеют неверный формат")


class EmailField(CharField):
    def validate(self, value: str | None) -> bool:
        if super().validate(value):
            if not value:
                return True
            if isinstance(value, str) and "@" in value:
                return True
        raise ValidationError("Поле email введено некорректно")


class PhoneField(Field):
    def validate(self, value: str | int | None) -> bool:
        super().validate(value)

        if not value:
            return True

        if type(value) not in (str, int):
            raise ValidationError("Номер телефона должно быть строкой или числом")

        value = str(value)

        if len(value) != 11:
            raise ValidationError("Номер телефона должен содержать 11 цифр")

        if value[0] != "7":
            raise ValidationError("Номер телефона должен начинаться с 7")

        return True


class DateField(Field):
    def validate(self, value: str) -> bool:
        super().validate(value)

        if not value:
            return True

        if not isinstance(value, str):
            raise ValidationError("Дата должна быть строкой в формате DD.MM.YYYY")

        try:
            datetime.datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            raise ValidationError("Дата должна быть в формате DD.MM.YYYY")

        return True


class BirthDayField(Field):
    def validate(self, value: str | None) -> bool:
        super().validate(value)
        if not value:
            return True

        if not isinstance(value, str):
            raise ValidationError(
                "Дата рождения должна быть строкой в формате DD.MM.YYYY"
            )

        try:
            birthday = datetime.datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            raise ValidationError("Дата рождения должна быть в формате DD.MM.YYYY")

        today = datetime.date.today()
        age_years = (today - birthday).days // 365
        if age_years > 70:
            raise ValidationError("Возраст не должен превышать 70 лет")

        if birthday > today:
            raise ValidationError("Введите действительную дату рождения")

        return True


class GenderField(Field):

    def validate(self, value: int | None) -> bool:
        super().validate(value)
        if not value:
            return True
        if not isinstance(value, int) or value not in [0, 1, 2]:
            raise ValidationError("Пол должен быть числом 0, 1 или 2")
        return True


class ClientIDsField(Field):
    def validate(self, value: list) -> bool:
        if not isinstance(value, list):
            raise ValidationError("Поле ID клиентов не является массивом")
        if len(value) == 0:
            raise ValidationError("client_ids не должен быть пустым")
        if not all(isinstance(i, (int, float)) for i in value):
            raise ValidationError("Поле ID клиентов должен содержать только числа")
        return True


class Request(ABC):

    def __init__(self, data: ArgumentsField | dict) -> None:
        if isinstance(data, dict):
            for name, field in self.__class__.__dict__.items():
                if isinstance(field, Field):
                    value = data.get(name)
                    try:
                        field.validate(value)
                    except ValidationError as e:
                        raise ValidationError(f"{name}: {e}")

                    setattr(self, name, value)

    @abstractmethod
    def get_value(self, value):
        pass


class ClientsInterestsRequest(Request):
    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)

    def __init__(self, data: ArgumentsField, store: Any):
        super().__init__(data)
        self.store = store

    def get_value(self, context: dict) -> dict[str, str]:
        interests_dict = {}
        if isinstance(self.client_ids, Sized) and isinstance(self.client_ids, Iterable):
            context["nclients"] = len(self.client_ids)
            for client_id in self.client_ids:
                interests = get_interests(store=self.store, cid=client_id)
                interests_dict[client_id] = interests
            return interests_dict
        raise ValidationError("Неверный формат ID клиентов")


class OnlineScoreRequest(Request):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    def __init__(self, data: dict | ArgumentsField, store: Any, is_admin: bool) -> None:
        super().__init__(data)
        self.store = store
        self.is_admin = is_admin

        if not self.validate():
            raise ValidationError(
                "Отсутствует хотя бы одна пара phone-email, "
                "first name-last name, gender-birthday с непустыми значениями."
            )

    def validate(self) -> bool:
        if self.phone is not None and self.email is not None:
            return True

        if self.first_name is not None and self.last_name is not None:
            return True

        if self.gender is not None and self.birthday is not None:
            return True

        return False

    def get_value(self, context) -> dict[str, Any]:
        if self.is_admin:
            return {"score": 42}

        has_fields = [
            field
            for field in (
                "phone",
                "email",
                "first_name",
                "last_name",
                "birthday",
                "gender",
            )
            if getattr(self, field) is not None
        ]
        context["has"] = has_fields

        score = get_score(
            store=self.store,
            phone=self.phone,
            email=self.email,
            birthday=(
                datetime.datetime.strptime(self.birthday, "%d.%m.%Y")
                if self.birthday
                else None
            ),
            gender=self.gender,
            first_name=self.first_name,
            last_name=self.last_name,
        )
        return {"score": score}


class MethodRequest(Request):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN

    def get_value(self, value):
        pass


def check_auth(request) -> bool:
    if request.is_admin:
        digest = hashlib.sha512(
            (datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).encode("utf-8")
        ).hexdigest()
    else:
        digest = hashlib.sha512(
            (request.account + request.login + SALT).encode("utf-8")
        ).hexdigest()
    return digest == request.token


def method_handler(request: dict, ctx: dict, store: Any) -> tuple:
    user_request: Request
    response: str | dict[str, Any]

    try:
        method = MethodRequest(request["body"])
    except ValidationError as e:
        response, code = str(e), INVALID_REQUEST
        return response, code

    if not check_auth(method):
        return "Forbidden", FORBIDDEN

    if method.method == "online_score":
        try:
            user_request = OnlineScoreRequest(method.arguments, store, method.is_admin)
            response, code = user_request.get_value(ctx), OK
        except ValidationError as e:
            response, code = str(e), INVALID_REQUEST

    if method.method == "clients_interests":
        try:
            user_request = ClientsInterestsRequest(method.arguments, store)
            response, code = user_request.get_value(ctx), OK
        except ValidationError as e:
            response, code = str(e), INVALID_REQUEST

    return response, code


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {"method": method_handler}
    store = Storage(RedisStore())

    def get_request_id(self, headers):
        return headers.get("HTTP_X_REQUEST_ID", uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            data_string = self.rfile.read(int(self.headers["Content-Length"]))
            request = json.loads(data_string)
        except Exception:
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path](
                        {"body": request, "headers": self.headers}, context, self.store
                    )
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}

        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r).encode("utf-8"))
        return


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", action="store", type=int, default=8080)
    parser.add_argument("-l", "--log", action="store", default=None)
    args = parser.parse_args()
    logging.basicConfig(
        filename=args.log,
        level=logging.INFO,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S",
    )
    server = HTTPServer(("localhost", args.port), MainHTTPHandler)
    logging.info("Starting server at %s" % args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
