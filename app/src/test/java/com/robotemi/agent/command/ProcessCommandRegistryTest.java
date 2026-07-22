package com.robotemi.agent.command;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

public class ProcessCommandRegistryTest {
    @Test
    public void duplicateCommandExecutesOnlyOnce() {
        ProcessCommandRegistry registry = new ProcessCommandRegistry(8);
        int executions = 0;

        if (registry.begin("cmd-1").getState()
                == ProcessCommandRegistry.BeginResult.State.FIRST_DELIVERY) {
            executions++;
        }
        if (registry.begin("cmd-1").getState()
                == ProcessCommandRegistry.BeginResult.State.FIRST_DELIVERY) {
            executions++;
        }

        assertEquals(1, executions);
    }

    @Test
    public void pendingDuplicateGetsOneDeterministicFinalReplay() {
        ProcessCommandRegistry registry = new ProcessCommandRegistry(8);
        registry.begin("cmd-1");
        ProcessCommandRegistry.BeginResult duplicate = registry.begin("cmd-1");

        assertEquals(ProcessCommandRegistry.BeginResult.State.DUPLICATE_PENDING,
                duplicate.getState());
        assertNull(duplicate.getResultPayload());
        assertEquals(1, registry.complete("cmd-1", "{\"status\":\"success\"}"));
    }

    @Test
    public void completedDuplicateReturnsExactCachedPayload() {
        ProcessCommandRegistry registry = new ProcessCommandRegistry(8);
        String payload = "{\"status\":\"success\",\"finished_at_ms\":123}";
        registry.begin("cmd-1");
        registry.complete("cmd-1", payload);

        ProcessCommandRegistry.BeginResult duplicate = registry.begin("cmd-1");

        assertEquals(ProcessCommandRegistry.BeginResult.State.DUPLICATE_COMPLETE,
                duplicate.getState());
        assertEquals(payload, duplicate.getResultPayload());
    }

    @Test
    public void registryIsBounded() {
        ProcessCommandRegistry registry = new ProcessCommandRegistry(2);
        registry.begin("cmd-1");
        registry.begin("cmd-2");
        ProcessCommandRegistry.BeginResult rejected = registry.begin("cmd-3");

        assertEquals(2, registry.size());
        assertEquals(ProcessCommandRegistry.BeginResult.State.CAPACITY_REJECTED,
                rejected.getState());
        assertEquals(ProcessCommandRegistry.BeginResult.State.DUPLICATE_PENDING,
                registry.begin("cmd-1").getState());
    }

    @Test
    public void validMediaExecutorIsInvokedOnce() {
        ProcessCommandRegistry registry = new ProcessCommandRegistry(8);
        int mediaExecutions = 0;

        if (registry.begin("cmd-media-1").getState()
                == ProcessCommandRegistry.BeginResult.State.FIRST_DELIVERY) {
            mediaExecutions++;
        }

        assertEquals(1, mediaExecutions);
    }

    @Test
    public void duplicateCommandDoesNotReplayMediaExecutor() {
        ProcessCommandRegistry registry = new ProcessCommandRegistry(8);
        int mediaExecutions = 0;

        if (registry.begin("cmd-media-1").getState()
                == ProcessCommandRegistry.BeginResult.State.FIRST_DELIVERY) {
            mediaExecutions++;
        }
        if (registry.begin("cmd-media-1").getState()
                == ProcessCommandRegistry.BeginResult.State.FIRST_DELIVERY) {
            mediaExecutions++;
        }

        assertEquals(1, mediaExecutions);
    }
}
