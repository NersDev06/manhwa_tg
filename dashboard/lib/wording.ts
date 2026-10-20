export function chaptersLabel(n: number) {
  const last = n % 10,
    lastTwo = n % 100;
  return (
    n.toLocaleString("ru") +
    " " +
    (last === 1 && lastTwo !== 11
      ? "глава"
      : last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)
        ? "главы"
        : "глав")
  );
}
