// Hand-drawn 24px line icons (1.6 stroke) — one consistent family, no emoji.
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 22, children, ...rest }: P & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const ArrowRight = (p: P) => (
  <Svg {...p}>
    <path d="M4 12h15M13 6l6 6-6 6" />
  </Svg>
);
export const ArrowUpRight = (p: P) => (
  <Svg {...p}>
    <path d="M7 17 17 7M8 7h9v9" />
  </Svg>
);
export const ArrowLeft = (p: P) => (
  <Svg {...p}>
    <path d="M20 12H5M11 6l-6 6 6 6" />
  </Svg>
);
export const Swap = (p: P) => (
  <Svg {...p}>
    <path d="M7 4v16M3 8l4-4 4 4M17 20V4M13 16l4 4 4-4" />
  </Svg>
);
export const Plus = (p: P) => (
  <Svg {...p}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);
export const Close = (p: P) => (
  <Svg {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Svg>
);
export const Check = (p: P) => (
  <Svg {...p}>
    <path d="m5 12.5 4.5 4.5L19 7" />
  </Svg>
);
/** half-filled circle — theme toggle */
export const Contrast = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 3.5a8.5 8.5 0 0 1 0 17Z" fill="currentColor" stroke="none" />
  </Svg>
);
export const Home = (p: P) => (
  <Svg {...p}>
    <path d="M4 10.5 12 4l8 6.5V20h-5.5v-5.5h-5V20H4Z" />
  </Svg>
);
export const Stack = (p: P) => (
  <Svg {...p}>
    <path d="m12 4 8 4-8 4-8-4Z" />
    <path d="m4 12 8 4 8-4M4 16l8 4 8-4" />
  </Svg>
);
/** road with dashed center line — orders / trips */
export const Road = (p: P) => (
  <Svg {...p}>
    <path d="M8 3 5 21M16 3l3 18" />
    <path d="M12 4v3M12 10.5v3M12 17v3" strokeDasharray="0" />
  </Svg>
);
export const User = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="8.5" r="3.8" />
    <path d="M4.5 20c1.2-3.6 4-5.3 7.5-5.3s6.3 1.7 7.5 5.3" />
  </Svg>
);
export const Search = (p: P) => (
  <Svg {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4 4" />
  </Svg>
);
export const Pen = (p: P) => (
  <Svg {...p}>
    <path d="M4 20h4L19 9l-4-4L4 16Z" />
    <path d="m13.5 6.5 4 4" />
  </Svg>
);
export const Inbox = (p: P) => (
  <Svg {...p}>
    <path d="M4 13 6.5 5h11L20 13v6H4Z" />
    <path d="M4 13h4.5l1 2h5l1-2H20" />
  </Svg>
);
export const Route = (p: P) => (
  <Svg {...p}>
    <circle cx="6" cy="18" r="2.2" />
    <circle cx="18" cy="6" r="2.2" />
    <path d="M8.2 18H15a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h6.8" />
  </Svg>
);
export const Truck = (p: P) => (
  <Svg {...p}>
    <path d="M3 6h11v10H3ZM14 9.5h3.5L21 13v3h-7" />
    <circle cx="7" cy="17.5" r="1.8" />
    <circle cx="17" cy="17.5" r="1.8" />
  </Svg>
);
export const Phone = (p: P) => (
  <Svg {...p}>
    <path d="M5 4h4l1.5 4.5-2.3 1.4a11 11 0 0 0 6 6l1.4-2.3L20 15v4a1.5 1.5 0 0 1-1.6 1.5C10.6 20 4 13.4 3.5 5.6A1.5 1.5 0 0 1 5 4Z" />
  </Svg>
);
export const Send = (p: P) => (
  <Svg {...p}>
    <path d="M20.5 4 3.5 11l6.5 2.5L12.5 20Z" />
    <path d="m10 13.5 4.5-4.5" />
  </Svg>
);
export const Pin = (p: P) => (
  <Svg {...p}>
    <path d="M12 21s6.5-5.6 6.5-11a6.5 6.5 0 0 0-13 0c0 5.4 6.5 11 6.5 11Z" />
    <circle cx="12" cy="10" r="2.3" />
  </Svg>
);
export const Bell = (p: P) => (
  <Svg {...p}>
    <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15Z" />
    <path d="M10 20.5a2.2 2.2 0 0 0 4 0" />
  </Svg>
);
export const Lock = (p: P) => (
  <Svg {...p}>
    <rect x="5" y="10.5" width="14" height="10" rx="2" />
    <path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5" />
  </Svg>
);
export const Camera = (p: P) => (
  <Svg {...p}>
    <path d="M4 8h3.5L9 5.5h6L16.5 8H20v11H4Z" />
    <circle cx="12" cy="13.2" r="3.3" />
  </Svg>
);
export const Star = ({ filled, ...p }: P & { filled?: boolean }) => (
  <Svg {...p}>
    <path
      d="m12 3.8 2.5 5.2 5.6.7-4.1 3.9 1 5.6-5-2.7-5 2.7 1-5.6-4.1-3.9 5.6-.7Z"
      fill={filled ? "currentColor" : "none"}
    />
  </Svg>
);
export const Alert = (p: P) => (
  <Svg {...p}>
    <path d="M12 4 21 19.5H3Z" />
    <path d="M12 10v4.2M12 17v.01" />
  </Svg>
);
export const Info = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 11v5.2M12 7.8v.01" />
  </Svg>
);
export const Car = (p: P) => (
  <Svg {...p}>
    <path d="M4 16.5V12l2-5h12l2 5v4.5Z" />
    <path d="M4 12h16" />
    <circle cx="7.5" cy="16.5" r="1.8" />
    <circle cx="16.5" cy="16.5" r="1.8" />
  </Svg>
);
export const ChevronRight = (p: P) => (
  <Svg {...p}>
    <path d="m9.5 5.5 6.5 6.5-6.5 6.5" />
  </Svg>
);
/** speech bubble — write a message */
export const Chat = (p: P) => (
  <Svg {...p}>
    <path d="M4.5 6.5a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H11l-4.5 3.5v-3.5h0a2 2 0 0 1-2-2Z" />
    <path d="M8.5 9.5h7M8.5 12.5h4.5" />
  </Svg>
);
/** car seat — passengers / free seats */
export const Seat = (p: P) => (
  <Svg {...p}>
    <path d="M8 4.5h3.2a1.8 1.8 0 0 1 1.8 1.9l-.5 7.1H17a2 2 0 0 1 2 2v1H8.6a2 2 0 0 1-2-1.7L5.9 6.6A1.8 1.8 0 0 1 8 4.5Z" />
    <path d="M9 16.5v3M16.5 16.5v3" />
  </Svg>
);
/** parcel box */
export const Box = (p: P) => (
  <Svg {...p}>
    <path d="m12 3.5 8 4v9l-8 4-8-4v-9Z" />
    <path d="m4 7.5 8 4 8-4M12 11.5v9M8 5.5l8 4" />
  </Svg>
);
export const Globe = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M3.5 12h17M12 3.5c2.3 2.4 3.4 5.2 3.4 8.5s-1.1 6.1-3.4 8.5c-2.3-2.4-3.4-5.2-3.4-8.5S9.7 5.9 12 3.5Z" />
  </Svg>
);
export const Help = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M9.6 9.6a2.5 2.5 0 0 1 4.8.9c0 1.7-2.4 2.1-2.4 3.6M12 16.8v.01" />
  </Svg>
);
export const FileText = (p: P) => (
  <Svg {...p}>
    <path d="M6 3.5h8l4 4v13H6Z" />
    <path d="M14 3.5v4h4M9 12h6M9 15.5h6" />
  </Svg>
);
export const Calendar = (p: P) => (
  <Svg {...p}>
    <rect x="4" y="5.5" width="16" height="14.5" rx="2" />
    <path d="M4 10h16M8.5 3.5v4M15.5 3.5v4" />
  </Svg>
);
export const Clock = (p: P) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 2" />
  </Svg>
);
export const Shield = (p: P) => (
  <Svg {...p}>
    <path d="M12 3.5 19 6v5.5c0 4.3-2.9 7.6-7 9-4.1-1.4-7-4.7-7-9V6Z" />
    <path d="m9 12 2.2 2.2L15.5 10" />
  </Svg>
);
/** licence plate */
export const Plate = (p: P) => (
  <Svg {...p}>
    <rect x="3" y="7.5" width="18" height="9" rx="2" />
    <path d="M6.5 12h.01M9.5 10.5v3M12.5 10.5v3M15.5 10.5v3" />
  </Svg>
);
/** weight — kg */
export const Weight = (p: P) => (
  <Svg {...p}>
    <path d="M7.2 8.5h9.6l2.2 11.5H5Z" />
    <circle cx="12" cy="5.8" r="2.3" />
  </Svg>
);
export const Wallet = (p: P) => (
  <Svg {...p}>
    <path d="M4 7.5a2 2 0 0 1 2-2h11v3" />
    <rect x="4" y="8.5" width="16" height="11" rx="2" />
    <path d="M16 14h.01" />
  </Svg>
);
