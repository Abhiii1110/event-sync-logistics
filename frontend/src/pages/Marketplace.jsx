import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errorMessage } from "../api/client";
import { CATEGORIES, categoryLabel } from "../utils/constants";
import { formatPaise } from "../utils/format";

function VendorCard({ vendor, category }) {
  const active = vendor.services.filter((s) => s.is_active);
  const relevant = category ? active.filter((s) => s.category === category) : active;
  const cheapest = relevant.length ? Math.min(...relevant.map((s) => s.price_paise)) : null;
  const categories = [...new Set(active.map((s) => s.category))];

  return (
    <Link to={`/vendors/${vendor.id}`} className="vendor-card">
      <h3>{vendor.business_name}</h3>
      <p className="muted-text">
        {vendor.city} · serves within {vendor.service_radius_km} km
      </p>
      {vendor.description && <p className="clamp">{vendor.description}</p>}
      <div className="chips">
        {categories.map((c) => (
          <span key={c} className="chip">{categoryLabel(c)}</span>
        ))}
      </div>
      <p className="price">
        {cheapest !== null ? `From ${formatPaise(cheapest)}` : "No services listed yet"}
      </p>
    </Link>
  );
}

export default function Marketplace() {
  const [cityInput, setCityInput] = useState("");
  const [city, setCity] = useState("");
  const [category, setCategory] = useState("");
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Wait until the user stops typing before calling the API
  useEffect(() => {
    const t = setTimeout(() => setCity(cityInput.trim()), 400);
    return () => clearTimeout(t);
  }, [cityInput]);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");

    api
      .get("/vendors/", {
        params: { city: city || undefined, category: category || undefined },
      })
      .then(({ data }) => {
        if (!ignore) setVendors(Array.isArray(data) ? data : data.results ?? []);
      })
      .catch((err) => {
        if (!ignore) setError(errorMessage(err));
      })
      .finally(() => {
        if (!ignore) setLoading(false);
      });

    return () => { ignore = true; };
  }, [city, category]);

  return (
    <div>
      <h2>Find event vendors</h2>

      <div className="filters panel">
        <label>City
          <input
            value={cityInput}
            onChange={(e) => setCityInput(e.target.value)}
            placeholder="e.g. Pune"
          />
        </label>
        <label>Category
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All categories</option>
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>{c.label}</option>
            ))}
          </select>
        </label>
      </div>

      {loading && <p className="center">Loading vendors...</p>}
      {error && <p className="error center">{error}</p>}
      {!loading && !error && vendors.length === 0 && (
        <p className="center muted-text">No vendors match these filters yet.</p>
      )}

      <div className="grid">
        {vendors.map((v) => (
          <VendorCard key={v.id} vendor={v} category={category} />
        ))}
      </div>
    </div>
  );
}