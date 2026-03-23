import pygame

def draw_world(screen, world, agents, cell_size=50, font=None):
    screen.fill((200, 200, 200))

    # сетка
    for y in range(world.height):
        for x in range(world.width):
            rect = pygame.Rect(x*cell_size, y*cell_size, cell_size, cell_size)
            color = (80,80,80) if world.grid[y,x] == 1 else (255,255,255)
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, (0,0,0), rect, 1)

    for agent in agents:
        # цель
        goal_center = (
            agent.goal_x*cell_size + cell_size//2,
            agent.goal_y*cell_size + cell_size//2
        )
        pygame.draw.circle(screen, (0, 200, 0), goal_center, cell_size//3)

        # агент
        rect = pygame.Rect(
            agent.x*cell_size+5,
            agent.y*cell_size+5,
            cell_size-10,
            cell_size-10
        )
        pygame.draw.rect(screen, (50, 100, 255), rect)

        
        if font:
            text = font.render(str(agent.id), True, (0, 0, 0))
            text_rect = text.get_rect(center=(
                agent.x*cell_size + cell_size//2,
                agent.y*cell_size + cell_size//2
            ))
            screen.blit(text, text_rect)

    pygame.display.flip()