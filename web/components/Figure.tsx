// Shows the exported number's own digits. Missing trailing zeros are padded
// invisibly so decimal points line up; nothing is rounded, and a fraction
// longer than `places` is shown whole.
export function Figure({ value, places = 0, signed = false }: { value: number; places?: number; signed?: boolean }) {
  const text = String(value);
  const fraction = text.split(".")[1] ?? "";
  const pad = places > fraction.length ? `${fraction ? "" : "."}${"0".repeat(places - fraction.length)}` : "";
  const tone = !signed || value === 0 ? "" : value > 0 ? "text-positive" : "text-negative";
  return (
    <span className={tone}>
      {signed && value > 0 ? "+" : ""}
      {text}
      {pad && (
        <span aria-hidden className="invisible select-none">
          {pad}
        </span>
      )}
    </span>
  );
}
