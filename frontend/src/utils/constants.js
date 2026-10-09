export const CATEGORIES = [
  { value: "FOOD_TRUCK", label: "Food Truck" },
  { value: "AV_CREW", label: "AV Setup Crew" },
  { value: "SECURITY", label: "Security Team" },
  { value: "DECOR", label: "Decor" },
];

export const categoryLabel = (value) =>
  CATEGORIES.find((c) => c.value === value)?.label || value;