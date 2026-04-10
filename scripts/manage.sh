#!/bin/bash

CONTAINER_NAME="h3xassist-bot"
COMMAND="${1:-help}"
shift || true

case $COMMAND in
    start)
        echo "Starting H3xAssist..."
        docker-compose up -d
        ;;
    stop)
        echo "Stopping H3xAssist..."
        docker-compose down
        ;;
    restart)
        echo "Restarting H3xAssist..."
        docker-compose restart
        ;;
    logs)
        docker-compose logs -f
        ;;
    status)
        docker-compose ps
        ;;
    shell)
        docker exec -it $CONTAINER_NAME /bin/bash
        ;;
    auth|teams-auth)
        ./scripts/teams-auth.sh "$@"
        ;;
    backup)
        echo "Backing up configuration and data..."
        BACKUP_DIR="./backup/$(date +%Y%m%d-%H%M%S)"
        mkdir -p "$BACKUP_DIR"
        
        docker run --rm \
            -v h3xassist-config:/source:ro \
            -v "$BACKUP_DIR":/dest \
            alpine tar czf /dest/config.tar.gz -C /source .
        
        docker run --rm \
            -v h3xassist-data:/source:ro \
            -v "$BACKUP_DIR":/dest \
            alpine tar czf /dest/data.tar.gz -C /source .
        
        echo "Backup complete: $BACKUP_DIR"
        ;;
    restore)
        BACKUP_FILE="$1"
        if [ -z "$BACKUP_FILE" ]; then
            echo "Usage: $0 restore <backup-dir>"
            echo "Example: $0 restore ./backup/20250110-120000"
            exit 1
        fi
        
        echo "Restoring from $BACKUP_FILE..."
        
        if [ -f "$BACKUP_FILE/config.tar.gz" ]; then
            docker run --rm \
                -v h3xassist-config:/dest \
                -v "$BACKUP_FILE":/source:ro \
                alpine tar xzf /source/config.tar.gz -C /dest
            echo "Config restored"
        fi
        
        if [ -f "$BACKUP_FILE/data.tar.gz" ]; then
            docker run --rm \
                -v h3xassist-data:/dest \
                -v "$BACKUP_FILE":/source:ro \
                alpine tar xzf /source/data.tar.gz -C /dest
            echo "Data restored"
        fi
        
        echo "Restore complete"
        ;;
    health)
        curl -s http://localhost:11411/health
        ;;
    audio-check)
        docker exec -it $CONTAINER_NAME /app/scripts/docker-audio-check.sh
        ;;
    validate-profile)
        docker exec -it $CONTAINER_NAME h3xassist validate-profile --online "$@"
        ;;
    clean)
        echo "Cleaning up unused resources..."
        docker-compose down -v
        docker system prune -f
        echo "Cleanup complete"
        ;;
    *)
        echo "H3xAssist Docker Management"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  start       - Start the service"
        echo "  stop        - Stop the service"
        echo "  restart     - Restart the service"
        echo "  logs        - View logs (Ctrl+C to exit)"
        echo "  status      - Show container status"
        echo "  shell       - Open shell in container"
        echo "  auth        - Authenticate Teams bot"
        echo "  backup      - Backup configuration and data"
        echo "  restore     - Restore from backup"
        echo "  health      - Check service health"
        echo "  audio-check - Check audio setup"
        echo "  validate-profile - Validate browser profile session"
        echo "  clean       - Remove container and volumes"
        echo ""
        ;;
esac
