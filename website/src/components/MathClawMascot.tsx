/**
 * MathClaw mascot. Used in Hero and Nav.
 */
import { LogoIcon } from "./LogoIcon";

interface MathClawMascotProps {
  size?: number;
  className?: string;
}

export function MathClawMascot({
  size = 80,
  className = "",
}: MathClawMascotProps) {
  return <LogoIcon size={size} className={className} />;
}
