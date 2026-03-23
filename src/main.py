import pygame
from core.world import World
from core.agent import Agent
from mapf.cbs import cbs
from simulation.simulator import Simulator
from visualization.render import draw_world

def main():
    pygame.init()
    font = None
    try:
        pygame.font.init()
        font = pygame.font.SysFont("Arial", 16)
        print("Font OK")
    except Exception as e:
        print("Font not available:", e)

    cell_size = 50
    screen = pygame.display.set_mode((500, 500))
    clock = pygame.time.Clock()

    world = World(10, 10, obstacles=[(3,y) for y in range(10) if y != 5])

    agents = [
        Agent(0, 0, 0, 6, 9),
        Agent(1, 6, 9, 0, 0),
        Agent(2, 0, 9, 6, 0),
    ]

    simulator = Simulator(world, agents, cbs)
    simulator.plan()

    running = True
    auto = True

    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False

        if auto:
            simulator.step()

        draw_world(screen, world, agents, cell_size, font)
        clock.tick(2)

    pygame.quit()

if __name__ == "__main__":
    main()