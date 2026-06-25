#!/bin/sh
set -e

# Variáveis injetadas via environment:
# POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD
# AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_S3_ENDPOINT_URL, BACKUP_BUCKET

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DAY_OF_WEEK=$(date +"%u")  # 1=segunda ... 7=domingo
FILENAME="dnimob_${TIMESTAMP}.sql.gz"
FILEPATH="/tmp/${FILENAME}"

echo "[backup] Iniciando backup: ${FILENAME}"

# 1. pg_dump
PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
	-h "${POSTGRES_HOST}" \
	-U "${POSTGRES_USER}" \
	-d "${POSTGRES_DB}" \
	--no-owner \
	--no-acl \
	| gzip > "${FILEPATH}"

echo "[backup] pg_dump concluído. Tamanho: $(du -sh ${FILEPATH} | cut -f1)"

# 2. Upload para B2 via aws cli (compatível S3)
aws s3 cp "${FILEPATH}" "s3://${BACKUP_BUCKET}/daily/${FILENAME}" \
	--endpoint-url "${AWS_S3_ENDPOINT_URL}" \
	--no-progress

echo "[backup] Upload daily/${FILENAME} concluído"

# 3. Se for domingo, copiar também para /weekly/
if [ "${DAY_OF_WEEK}" = "7" ]; then
	WEEKLY_NAME="dnimob_weekly_${TIMESTAMP}.sql.gz"
	aws s3 cp "${FILEPATH}" "s3://${BACKUP_BUCKET}/weekly/${WEEKLY_NAME}" \
		--endpoint-url "${AWS_S3_ENDPOINT_URL}" \
		--no-progress
	echo "[backup] Upload weekly/${WEEKLY_NAME} concluído"
fi

# 4. Limpeza local
rm -f "${FILEPATH}"

# 5. Retenção: deletar daily/ com mais de 7 dias
echo "[backup] Aplicando retenção (daily > 7 dias)..."
CUTOFF=$(date -d "7 days ago" +"%Y%m%d" 2>/dev/null || date -v-7d +"%Y%m%d")

aws s3 ls "s3://${BACKUP_BUCKET}/daily/" \
	--endpoint-url "${AWS_S3_ENDPOINT_URL}" \
	| awk '{print $4}' \
	| while read -r key; do
		FILE_DATE=$(echo "${key}" | grep -oE '[0-9]{8}' | head -1)
		if [ -n "${FILE_DATE}" ] && [ "${FILE_DATE}" -lt "${CUTOFF}" ]; then
			echo "[backup] Deletando daily/${key} (${FILE_DATE} < ${CUTOFF})"
			aws s3 rm "s3://${BACKUP_BUCKET}/daily/${key}" \
				--endpoint-url "${AWS_S3_ENDPOINT_URL}"
		fi
	done

# 6. Retenção: manter apenas 4 backups semanais
echo "[backup] Aplicando retenção (weekly > 4 arquivos)..."
aws s3 ls "s3://${BACKUP_BUCKET}/weekly/" \
	--endpoint-url "${AWS_S3_ENDPOINT_URL}" \
	| awk '{print $4}' \
	| sort \
	| head -n -4 \
	| while read -r key; do
		echo "[backup] Deletando weekly/${key}"
		aws s3 rm "s3://${BACKUP_BUCKET}/weekly/${key}" \
			--endpoint-url "${AWS_S3_ENDPOINT_URL}"
	done

echo "[backup] Backup finalizado com sucesso: ${FILENAME}"