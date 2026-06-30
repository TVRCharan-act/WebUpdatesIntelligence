"use client";

import * as React from "react";

import { usePathname } from "@/components/router";
import { recordHealthEvent } from "@/lib/health-events";

export function RouteLogger() {
  const pathname = usePathname();

  React.useEffect(() => {
    recordHealthEvent({
      event_type: "frontend_route",
      action: "route_view",
      metadata: { pathname },
    });
  }, [pathname]);

  return null;
}
