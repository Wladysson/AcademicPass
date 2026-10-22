package org.enade.simulado.api;

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
        Map<String, Object> response = Map.of(
                "service", "simulado-service",
                "status", "UP",
                "timestamp", Instant.now().toString()
        );

        return Response.ok(response).build();
    }

    @GET
    @Path("/ready")
    public Response readiness() {
        Map<String, Object> response = Map.of(
                "service", "simulado-service",
                "status", "READY",
                "timestamp", Instant.now().toString()
        );

        return Response.ok(response).build();
    }
}