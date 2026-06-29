"use client";

import { usePathname } from "next/navigation";
import * as React from "react";

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
