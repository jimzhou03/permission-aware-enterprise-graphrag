export type IconProps = {
  className?: string;
};

function stroke(className: string | undefined): string {
  return className ?? "h-4 w-4";
}

export function BrandGraphIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="12" cy="6.5" r="1.6" fill="currentColor" />
      <circle cx="17.3" cy="15.5" r="1.6" fill="currentColor" />
      <circle cx="6.7" cy="15.5" r="1.6" fill="currentColor" />
      <path d="M10.8 7.7 7.8 14M13.2 7.7l3 6.3M8.4 14.8h7.2" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

export function GlobeIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.8" />
      <path d="M3.5 12h17M12 3.5c2.3 2.2 3.6 5.2 3.6 8.5S14.3 18.3 12 20.5M12 3.5c-2.3 2.2-3.6 5.2-3.6 8.5S9.7 18.3 12 20.5" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

export function UserIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <circle cx="12" cy="8" r="3.2" stroke="currentColor" strokeWidth="1.8" />
      <path d="M5.5 19.2c1.4-3.1 4-4.7 6.5-4.7s5.1 1.6 6.5 4.7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function LogoutIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4" stroke="currentColor" strokeWidth="1.8" />
      <path d="m14 8 4 4-4 4M18 12H9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ChatIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <path d="M4.5 6.5A2.5 2.5 0 0 1 7 4h10a2.5 2.5 0 0 1 2.5 2.5v6A2.5 2.5 0 0 1 17 15h-5.6l-3.7 3.2c-.6.5-1.5.1-1.5-.7V15H7a2.5 2.5 0 0 1-2.5-2.5v-6Z" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="9" cy="9.5" r="1" fill="currentColor" />
      <circle cx="12" cy="9.5" r="1" fill="currentColor" />
      <circle cx="15" cy="9.5" r="1" fill="currentColor" />
    </svg>
  );
}

export function DatabaseIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <ellipse cx="12" cy="6.5" rx="6.5" ry="2.8" stroke="currentColor" strokeWidth="1.8" />
      <path d="M5.5 6.5v4c0 1.5 2.9 2.8 6.5 2.8s6.5-1.3 6.5-2.8v-4M5.5 10.5v4c0 1.5 2.9 2.8 6.5 2.8s6.5-1.3 6.5-2.8v-4" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

export function AuditIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <rect x="6" y="4.5" width="12" height="15" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <path d="M9 9h6M9 12h6M9 15h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function SystemIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M19.5 12a7.5 7.5 0 0 0-.1-1l2-1.6-1.8-3.1-2.4.8a7.7 7.7 0 0 0-1.7-1l-.4-2.5h-3.6l-.4 2.5a7.7 7.7 0 0 0-1.7 1l-2.4-.8-1.8 3.1 2 1.6a7.8 7.8 0 0 0 0 2l-2 1.6 1.8 3.1 2.4-.8c.5.4 1.1.8 1.7 1l.4 2.5h3.6l.4-2.5c.6-.2 1.2-.6 1.7-1l2.4.8 1.8-3.1-2-1.6c.1-.4.1-.7.1-1Z" stroke="currentColor" strokeWidth="1.1" strokeLinejoin="round" />
    </svg>
  );
}

export function TraceIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <circle cx="6.5" cy="6.5" r="2.3" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="17.5" cy="12" r="2.3" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="8.5" cy="18" r="2.3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M8.3 7.7 15 10.8M15.5 13.7l-5.7 2.8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function GraphIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <circle cx="5.5" cy="12" r="2.3" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="12" cy="6" r="2.3" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="18.5" cy="12.5" r="2.3" stroke="currentColor" strokeWidth="1.8" />
      <circle cx="12" cy="18" r="2.3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M7.5 10.8 10 7.8M14 7.8l2.7 2.9M16.7 14.3 14 16.2M10 16.2l-2.6-2.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function PlusIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function TrashIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <path d="M4 7h16M9 7V5.6c0-.9.7-1.6 1.6-1.6h2.8c.9 0 1.6.7 1.6 1.6V7M7 7l.8 11.1c.1 1 .9 1.8 1.9 1.8h4.6c1 0 1.8-.8 1.9-1.8L17 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M10 11v5M14 11v5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function MicIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <rect x="9" y="4" width="6" height="10" rx="3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M6.5 11.5a5.5 5.5 0 0 0 11 0M12 17v3M9 20h6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function SendIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <path d="M4 12.3 19 5l-3 14-4.8-4.8L4 12.3Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M11.2 14.2 19 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function MailIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <rect x="3.5" y="5.5" width="17" height="13" rx="2.2" stroke="currentColor" strokeWidth="1.8" />
      <path d="m5 7 7 5 7-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ShieldIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <path d="M12 4.5 5.5 7v5.2c0 4 2.6 6.8 6.5 7.8 3.9-1 6.5-3.8 6.5-7.8V7L12 4.5Z" stroke="currentColor" strokeWidth="1.8" />
      <path d="m9.8 12 1.6 1.7 3-3.3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function BuildingIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" className={stroke(className)} aria-hidden="true">
      <path d="M4.5 19.5h15M7 19.5V6.8c0-.7.4-1.3 1-1.6L12 3l4 2.2c.6.3 1 .9 1 1.6v12.7" stroke="currentColor" strokeWidth="1.8" />
      <path d="M10 9h1M13 9h1M10 12h1M13 12h1M11 19.5v-3h2v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
