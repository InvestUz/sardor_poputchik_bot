import { useEffect } from "react";
import { MemoryRouter, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { Home as HomeIcon, Info, Route as RouteIcon, Stack, User } from "./components/icons";
import { EmptyState, Loading } from "./components/ui";
import CarrierSetup from "./pages/CarrierSetup";
import CreateListing from "./pages/CreateListing";
import Home from "./pages/Home";
import ListingDetail from "./pages/ListingDetail";
import MyListings from "./pages/MyListings";
import OrderDetail from "./pages/OrderDetail";
import Orders from "./pages/Orders";
import Profile from "./pages/Profile";
import Search from "./pages/Search";
import UserTrust from "./pages/UserTrust";
import { useApp } from "./store";
import { tg } from "./tg";

// Deep links from bot notifications open /app/?p=/orders/5
function initialPath(): string {
  const p = new URLSearchParams(window.location.search).get("p");
  return p && p.startsWith("/") ? p : "/";
}

const TABS = ["/", "/my", "/orders", "/profile"];

function TelegramBackButton() {
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const w = tg();
    if (!w) return;
    const back = () => navigate(-1);
    if (TABS.includes(location.pathname)) w.BackButton.hide();
    else {
      w.BackButton.show();
      w.BackButton.onClick(back);
    }
    return () => w.BackButton.offClick(back);
  }, [location, navigate]);
  return null;
}

function ScrollTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [pathname]);
  return null;
}

function Shell() {
  const { me, t, loadError, config } = useApp();
  let gate: string | null = null;
  if (loadError) gate = t(`err.${loadError}`);
  else if (me && !me.registered) gate = t("home.not_registered");
  else if (me?.blocked) gate = t("home.blocked", { support: config?.support_contact ?? "" });

  if (gate)
    return (
      <main className="page">
        <EmptyState icon={<Info size={44} />} title="Yo'lchi" text={gate} />
      </main>
    );
  if (!me || !config) return <Loading />;

  return (
    <>
      <TelegramBackButton />
      <ScrollTop />
      <main className="page">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/search/:kind" element={<Search />} />
          <Route path="/create/:kind" element={<CreateListing />} />
          <Route path="/listings/:id" element={<ListingDetail />} />
          <Route path="/my" element={<MyListings />} />
          <Route path="/orders" element={<Orders />} />
          <Route path="/orders/:id" element={<OrderDetail />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/carrier" element={<CarrierSetup />} />
          <Route path="/users/:id" element={<UserTrust />} />
          <Route path="*" element={<Home />} />
        </Routes>
      </main>
      <nav className="tabbar" aria-label={t("nav.home")}>
        <NavLink to="/" end aria-label={t("nav.home")}>
          <HomeIcon size={24} />
          <span className="lbl">{t("nav.home")}</span>
        </NavLink>
        <NavLink to="/my" aria-label={t("nav.my")}>
          <Stack size={24} />
          <span className="lbl">{t("nav.my")}</span>
        </NavLink>
        <NavLink to="/orders" aria-label={t("nav.orders")}>
          <RouteIcon size={24} />
          <span className="lbl">{t("nav.orders")}</span>
        </NavLink>
        <NavLink to="/profile" aria-label={t("nav.profile")}>
          <User size={24} />
          <span className="lbl">{t("nav.profile")}</span>
        </NavLink>
      </nav>
    </>
  );
}

export default function App() {
  return (
    <MemoryRouter initialEntries={[initialPath()]}>
      <Shell />
    </MemoryRouter>
  );
}
