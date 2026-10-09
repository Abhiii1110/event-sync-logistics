import { useEffect, useState } from "react";
import { Link,useLocation, useNavigate, useParams } from "react-router-dom";
import api, { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import AvailabilityCalendar from "../components/AvailabilityCalendar";
import { categoryLabel } from "../utils/constants";
import { formatDuration, formatPaise } from "../utils/format";
import { dateTimeLabel, timeLabel } from "../utils/time";

export default function VendorDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const location = useLocation();
  const notice = location.state?.notice;

  const [vendor, setVendor] = useState(null);
  const [state, setState] = useState("loading");   // loading | ready | notfound | error
  const [error, setError] = useState("");
  const [serviceId, setServiceId] = useState(null);
  const [slot, setSlot] = useState(null);           // chosen start time (a Date)

  useEffect(() => {
    let ignore = false;
    setState("loading");

    api
      .get(`/vendors/${id}/`)
      .then(({ data }) => {
        if (ignore) return;
        setVendor(data);
        const first = data.services.find((s) => s.is_active);
        setServiceId(first ? first.id : null);
        setState("ready");
      })
      .catch((err) => {
        if (ignore) return;
        if (err.response?.status === 404) {
          setState("notfound");
        } else {
          setError(errorMessage(err));
          setState("error");
        }
      });

    return () => { ignore = true; };
  }, [id]);

  if (state === "loading") return <p className="center">Loading...</p>;
  if (state === "notfound") {
    return <p className="center">Vendor not found. <Link to="/vendors">Back to marketplace</Link></p>;
  }
  if (state === "error") return <p className="error center">{error}</p>;

  const services = vendor.services.filter((s) => s.is_active);
  const service = services.find((s) => s.id === serviceId);
  const endTime = slot && service ? new Date(slot.getTime() + service.duration_minutes * 60000) : null;

  const chooseService = (sid) => {
    setServiceId(sid);
    setSlot(null);        // a different service has a different duration
  };

  const goToBooking = () => {
    navigate("/book", {
      state: {
        vendorId: vendor.id,
        vendorName: vendor.business_name,
        serviceId: service.id,
        serviceTitle: service.title,
        pricePaise: service.price_paise,
        durationMinutes: service.duration_minutes,
        startISO: slot.toISOString(),
      },
    });
  };

  let action;
  if (!user) {
    action = <button onClick={() => navigate("/login")}>Log in to book</button>;
  } else if (user.role === "CLIENT") {
    action = <button onClick={goToBooking}>Continue to booking</button>;
  } else {
    action = <p className="muted-text">Only client accounts can book services.</p>;
  }

  return (
    <div>
      <p><Link to="/vendors">&larr; All vendors</Link></p>
         {notice && <p className="notice">{notice}</p>}

      <div className="panel">
        <h2>{vendor.business_name}</h2>
        <p className="muted-text">
          {vendor.city} · serves within {vendor.service_radius_km} km
        </p>
        {vendor.description && <p>{vendor.description}</p>}
      </div>

      <div className="panel">
        <h3>1. Choose a service</h3>
        {services.length === 0 && <p className="muted-text">This vendor has no active services yet.</p>}
        {services.map((s) => (
          <label key={s.id} className={`service-option ${s.id === serviceId ? "active" : ""}`}>
            <input
              type="radio"
              name="service"
              checked={s.id === serviceId}
              onChange={() => chooseService(s.id)}
            />
            <div>
              <strong>{s.title}</strong>
              <div className="muted-text">
                {categoryLabel(s.category)} · {formatDuration(s.duration_minutes)}
              </div>
              {s.description && <div>{s.description}</div>}
            </div>
            <span className="price">{formatPaise(s.price_paise)}</span>
          </label>
        ))}
      </div>

      {service && (
        <div className="panel">
          <h3>2. Pick a start time</h3>
          <p className="muted-text">
            Times are in India time. Your event runs {formatDuration(service.duration_minutes)} from the start.
          </p>
          <AvailabilityCalendar
            key={service.id}
            vendorId={vendor.id}
            service={service}
            selected={slot}
            onSelect={setSlot}
          />
        </div>
      )}

      {service && slot && (
        <div className="panel summary">
          <h3>Your selection</h3>
          <p><strong>{service.title}</strong> with {vendor.business_name}</p>
          <p>{dateTimeLabel(slot)} to {timeLabel(endTime)}</p>
          <p className="price">{formatPaise(service.price_paise)}</p>
          {action}
        </div>
      )}
    </div>
  );
}