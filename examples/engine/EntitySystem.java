package engine;

import java.util.*;

public class EntitySystem {

    static class Entity {
        int x, y;
    }

    List<Entity> entities = new ArrayList<>();

    public void update() {
        for (Entity e : entities) {
            e.x += 1;
            e.y += 1;
        }
    }
}