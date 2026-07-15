export default function FitBadge({ score, category }) {
  if (score == null) return <span className="badge badge-unknown">—</span>;
  return (
    <span className={`badge badge-${category || "weak"}`} title={`Fit category: ${category}`}>
      {Number(score).toFixed(2)}
    </span>
  );
}

export function categoryLabel(category) {
  return (
    { strong: "Strong fit", good: "Good fit", maybe: "Maybe fit", weak: "Weak fit" }[category] ||
    "Unscored"
  );
}
