import {
  BotIcon,
  GitBranchIcon,
  HouseIcon,
  MoonIcon,
  SearchIcon,
  Settings2Icon,
  SunIcon,
} from "lucide-react";
import { useTheme } from "next-themes";
import { Link, useLocation } from "@/lib/routing";
import { XwavIcon } from "@/components/icons/XwavIcon";

/** Persistent desktop navigation; mobile keeps the accessible sidebar drawer. */
export function WorkbenchRail({ onSearch }: { onSearch: () => void }) {
  const { pathname } = useLocation();
  const { resolvedTheme, setTheme } = useTheme();
  const dark = resolvedTheme === "dark";
  const destinations = [
    { to: "/", label: "Workspace home", icon: HouseIcon, active: pathname === "/" },
    {
      to: "/settings/harnesses",
      label: "Harness settings",
      icon: BotIcon,
      active: pathname.startsWith("/settings/harnesses"),
    },
    {
      to: "/settings/git",
      label: "Git connections",
      icon: GitBranchIcon,
      active: pathname.startsWith("/settings/git"),
    },
  ];
  return (
    <nav aria-label="Xwav workbench" className="xwav-rail">
      <Link to="/" aria-label="Xwav home" className="xwav-rail-brand">
        <XwavIcon className="size-7" />
      </Link>
      <div className="xwav-rail-links">
        {destinations.map(({ to, label, icon: Icon, active }) => (
          <Link
            key={to}
            to={to}
            aria-label={label}
            title={label}
            aria-current={active ? "page" : undefined}
            className="xwav-rail-action"
          >
            <Icon className="size-5" />
          </Link>
        ))}
        <button
          type="button"
          onClick={onSearch}
          aria-label="Search workspace"
          title="Search workspace"
          className="xwav-rail-action"
        >
          <SearchIcon className="size-5" />
        </button>
      </div>
      <div className="xwav-rail-bottom">
        <button
          type="button"
          onClick={() => setTheme(dark ? "light" : "dark")}
          aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
          title={dark ? "Switch to light mode" : "Switch to dark mode"}
          className="xwav-rail-action"
        >
          {dark ? <SunIcon className="size-5" /> : <MoonIcon className="size-5" />}
        </button>
        <Link
          to="/settings/appearance"
          aria-label="Workbench appearance"
          title="Workbench appearance"
          className="xwav-rail-action"
        >
          <Settings2Icon className="size-5" />
        </Link>
        <span className="xwav-rail-monogram" aria-hidden="true">
          XW
        </span>
      </div>
    </nav>
  );
}
