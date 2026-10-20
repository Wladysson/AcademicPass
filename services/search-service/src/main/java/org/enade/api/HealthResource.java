package org.enade.search.api;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;

import java.time.Instant;
import java.util.Map;

@Path("/api/v1/health")
@Produces(MediaType.APPLICATION_JSON)
public class HealthResource {

    @GET
    public Response health() {
        return Response.ok(Map.of(
                "service", "search-service",
                "status", "UP",
                "timestamp", Instant.now().toString()
        )).build();
    }

    @GET
    @Path("/readiness")
    public Response readiness() {
        return Response.ok(Map.of(
                "service", "search-service",
                "status", "READY",
                "timestamp", Instant.now().toString()
        )).build();
    }
}
