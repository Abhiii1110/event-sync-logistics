import { useAuth } from "../auth/AuthContext";

export default function Dashboard() {
  const { user } = useAuth();
  return (
    <div className="card">
      <h2>Welcome, {user.username}</h2>
      <p>Role: <strong>{user.role}</strong></p>
      <p>Email: {user.email}</p>
      <p>
        {user.role === "VENDOR"
          ? "Next we will add your services, bookings and earnings here."
          : "Next we will add the vendor marketplace and your bookings here."}
      </p>
    </div>
  );
}