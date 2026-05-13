package engine;

public class ChunkEngine {

    int[][][] blocks = new int[16][256][16];

    public void set(int x, int y, int z, int id) {
        blocks[x][y][z] = id;
    }

    public void tick() {
        for (int x = 0; x < 16; x++)
        for (int y = 0; y < 256; y++)
        for (int z = 0; z < 16; z++) {
            if (blocks[x][y][z] != 0) {
                blocks[x][y][z]++;
            }
        }
    }
}