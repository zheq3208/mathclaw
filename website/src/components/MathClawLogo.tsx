/**
 * MathClaw logo: symbol only.
 */
import { LogoIcon } from "./LogoIcon";

interface MathClawLogoProps {
  variant?: "full" | "mark";
  size?: number;
  animated?: boolean;
  className?: string;
}

export function MathClawLogo({
  variant = "full",
  size = 48,
  animated: _animated = false,
  className = "",
}: MathClawLogoProps) {
  const markSize = variant === "mark" ? size : Math.round(size * 1.1);
  return (
    <span
      className={className}
      style={{ display: "inline-flex", alignItems: "center", lineHeight: 1 }}
    >
      <LogoIcon size={markSize} />
    </span>
  );
}
