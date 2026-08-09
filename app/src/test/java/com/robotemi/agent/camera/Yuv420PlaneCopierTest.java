package com.robotemi.agent.camera;

import static org.junit.Assert.assertArrayEquals;

import org.junit.Test;

import java.nio.ByteBuffer;
import java.util.Arrays;

public class Yuv420PlaneCopierTest {
    @Test
    public void packedRowsCopyOnlyVisiblePixels() {
        ByteBuffer source = ByteBuffer.wrap(new byte[] {
                1, 2, 3, 4, 90, 91,
                5, 6, 7, 8, 92, 93
        });
        byte[] target = filled(12, (byte) -1);

        Yuv420PlaneCopier.copy(
                source,
                6,
                1,
                4,
                2,
                target,
                1,
                5,
                1,
                null);

        assertArrayEquals(
                new byte[] {-1, 1, 2, 3, 4, -1, 5, 6, 7, 8, -1, -1},
                target);
    }

    @Test
    public void stridedRowsDiscardInterleavedBytes() {
        ByteBuffer source = ByteBuffer.wrap(new byte[] {
                1, 90, 2, 91, 3, 92, 4, 93,
                5, 94, 6, 95, 7, 96, 8, 97
        });
        byte[] target = new byte[8];

        Yuv420PlaneCopier.copy(
                source,
                8,
                2,
                4,
                2,
                target,
                0,
                4,
                1,
                new byte[8]);

        assertArrayEquals(new byte[] {1, 2, 3, 4, 5, 6, 7, 8}, target);
    }

    @Test
    public void stridedRowsHonorTargetPixelStride() {
        ByteBuffer source = ByteBuffer.wrap(new byte[] {1, 90, 2, 91, 3, 92, 4, 93});
        byte[] target = filled(8, (byte) -1);

        Yuv420PlaneCopier.copy(
                source,
                8,
                2,
                4,
                1,
                target,
                0,
                8,
                2,
                new byte[8]);

        assertArrayEquals(new byte[] {1, -1, 2, -1, 3, -1, 4, -1}, target);
    }

    @Test(expected = IllegalArgumentException.class)
    public void stridedRowsRejectUndersizedScratchBuffer() {
        Yuv420PlaneCopier.copy(
                ByteBuffer.wrap(new byte[8]),
                8,
                2,
                4,
                1,
                new byte[4],
                0,
                4,
                1,
                new byte[7]);
    }

    private static byte[] filled(int length, byte value) {
        byte[] result = new byte[length];
        Arrays.fill(result, value);
        return result;
    }
}
