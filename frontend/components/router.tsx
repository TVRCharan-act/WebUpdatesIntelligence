import * as React from "react";

type RouterContextValue = {
  pathname: string;
  push: (href: string) => void;
  replace: (href: string) => void;
};

const RouterContext = React.createContext<RouterContextValue | null>(null);

function currentPathname() {
  return window.location.pathname || "/";
}

function useRouterContext() {
  const context = React.useContext(RouterContext);

  if (!context) {
    throw new Error("Router hooks must be used inside RouterProvider.");
  }

  return context;
}

export function RouterProvider({ children }: { children: React.ReactNode }) {
  const [pathname, setPathname] = React.useState(currentPathname);

  React.useEffect(() => {
    const handlePopState = () => setPathname(currentPathname());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const updatePath = React.useCallback((href: string, replace = false) => {
    const url = new URL(href, window.location.href);

    if (url.origin !== window.location.origin) {
      window.location.assign(url.href);
      return;
    }

    const nextPath = url.pathname || "/";
    const nextUrl = `${nextPath}${url.search}${url.hash}`;

    if (replace) {
      window.history.replaceState(null, "", nextUrl);
    } else if (nextUrl !== `${window.location.pathname}${window.location.search}${window.location.hash}`) {
      window.history.pushState(null, "", nextUrl);
    }

    setPathname(nextPath);
    window.scrollTo({ top: 0, left: 0 });
  }, []);

  const value = React.useMemo(
    () => ({
      pathname,
      push: (href: string) => updatePath(href),
      replace: (href: string) => updatePath(href, true),
    }),
    [pathname, updatePath],
  );

  return (
    <RouterContext.Provider value={value}>{children}</RouterContext.Provider>
  );
}

export function usePathname() {
  return useRouterContext().pathname;
}

export function useRouter() {
  const { push, replace } = useRouterContext();
  return { push, replace };
}

export function useParams<T extends Record<string, string>>() {
  const pathname = usePathname();
  const sourceMatch = pathname.match(/^\/sources\/([^/]+)$/);

  if (sourceMatch) {
    return { id: decodeURIComponent(sourceMatch[1]) } as unknown as T;
  }

  return {} as T;
}

export interface LinkProps
  extends Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  href: string;
}

export const Link = React.forwardRef<HTMLAnchorElement, LinkProps>(
  ({ href, onClick, target, ...props }, ref) => {
    const router = useRouter();

    return (
      <a
        ref={ref}
        href={href}
        target={target}
        onClick={(event) => {
          onClick?.(event);

          if (
            event.defaultPrevented ||
            target ||
            event.button !== 0 ||
            event.metaKey ||
            event.altKey ||
            event.ctrlKey ||
            event.shiftKey
          ) {
            return;
          }

          const url = new URL(href, window.location.href);

          if (url.origin !== window.location.origin) {
            return;
          }

          event.preventDefault();
          router.push(`${url.pathname}${url.search}${url.hash}`);
        }}
        {...props}
      />
    );
  },
);

Link.displayName = "Link";
