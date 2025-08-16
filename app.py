from fastapi import FastAPI, Request, Form, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from typing import Dict

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="change-this-secret")  # for login session

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ---------- Domain Models ----------
class Flight:
    def __init__(self, flight_number: str, origin: str, destination: str, seat_capacity: int):
        self.flight_number = flight_number
        self.origin = origin
        self.destination = destination
        self.seat_capacity = seat_capacity
        self.available_seats = seat_capacity
        self.bookings: Dict[str, str] = {}  # seat -> passenger_name

    def book_seat(self, passenger_name: str, seat_number: str) -> bool:
        if self.available_seats <= 0:
            return False
        if seat_number in self.bookings:
            return False
        # Validate seat_number within capacity
        try:
            s = int(seat_number)
            if s < 1 or s > self.seat_capacity:
                return False
        except ValueError:
            return False

        self.bookings[seat_number] = passenger_name
        self.available_seats -= 1
        return True

    def cancel_booking(self, seat_number: str) -> bool:
        if seat_number not in self.bookings:
            return False
        del self.bookings[seat_number]
        self.available_seats += 1
        return True


# ---------- In-memory Data Stores ----------
FLIGHTS: Dict[str, Flight] = {}
USERS: Dict[str, str] = {}  # username -> password


# ---------- Helpers ----------
def current_user(request: Request):
    return request.session.get("user")


def require_login(request: Request):
    return current_user(request) is not None


# ---------- Routes ----------
@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "user": current_user(request)}
    )


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username in USERS and USERS[username] == password:
        request.session["user"] = username
        return RedirectResponse(url="/flights", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid username or password"})


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@app.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...)):
    if username in USERS:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Username already exists"})
    USERS[username] = password
    request.session["user"] = username
    return RedirectResponse(url="/flights", status_code=status.HTTP_302_FOUND)


@app.get("/flights", response_class=HTMLResponse)
def show_flights(request: Request):
    return templates.TemplateResponse(
        "flights.html",
        {"request": request, "flights": FLIGHTS.values(), "user": current_user(request)}
    )


@app.get("/flights/add", response_class=HTMLResponse)
def add_flight_page(request: Request):
    if not require_login(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("add_flight.html", {"request": request, "error": None})


@app.post("/flights/add")
def add_flight(
    request: Request,
    flight_number: str = Form(...),
    origin: str = Form(...),
    destination: str = Form(...),
    seat_capacity: int = Form(...)
):
    if not require_login(request):
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

    fn = flight_number.strip().upper()
    if fn in FLIGHTS:
        return templates.TemplateResponse("add_flight.html", {"request": request, "error": "Flight number already exists!"})

    FLIGHTS[fn] = Flight(fn, origin.strip().title(), destination.strip().title(), seat_capacity)
    return RedirectResponse(url="/flights", status_code=status.HTTP_302_FOUND)


@app.get("/flights/{flight_number}/book", response_class=HTMLResponse)
def book_page(request: Request, flight_number: str):
    fn = flight_number.upper()
    flight = FLIGHTS.get(fn)
    if not flight:
        return RedirectResponse(url="/flights", status_code=status.HTTP_302_FOUND)

    available_seats = [str(s) for s in range(1, flight.seat_capacity + 1) if str(s) not in flight.bookings]
    return templates.TemplateResponse(
        "book.html",
        {"request": request, "flight": flight, "available_seats": available_seats, "error": None, "user": current_user(request)}
    )


@app.post("/flights/{flight_number}/book")
def book(
    request: Request,
    flight_number: str,
    passenger_name: str = Form(...),
    seat_number: str = Form(...)
):
    fn = flight_number.upper()
    flight = FLIGHTS.get(fn)
    if not flight:
        return RedirectResponse(url="/flights", status_code=status.HTTP_302_FOUND)

    ok = flight.book_seat(passenger_name.strip(), seat_number.strip())
    if not ok:
        available_seats = [str(s) for s in range(1, flight.seat_capacity + 1) if str(s) not in flight.bookings]
        return templates.TemplateResponse(
            "book.html",
            {"request": request, "flight": flight, "available_seats": available_seats, "error": "Seat not available or invalid.", "user": current_user(request)}
        )
    return RedirectResponse(url="/flights", status_code=status.HTTP_302_FOUND)


@app.post("/flights/{flight_number}/cancel")
def cancel(request: Request, flight_number: str, seat_number: str = Form(...)):
    fn = flight_number.upper()
    flight = FLIGHTS.get(fn)
    if flight:
        flight.cancel_booking(seat_number.strip())
    return RedirectResponse(url="/flights", status_code=status.HTTP_302_FOUND)


# Seed demo flights (optional)
@app.on_event("startup")
def seed():
    if "AI101" not in FLIGHTS:
        FLIGHTS["AI101"] = Flight("AI101", "Mumbai", "Delhi", 6)
    if "6E220" not in FLIGHTS:
        FLIGHTS["6E220"] = Flight("6E220", "Bengaluru", "Hyderabad", 4)
